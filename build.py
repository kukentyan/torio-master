import os
import sys
import shutil
import subprocess
from pathlib import Path
import time

class PydBuilder:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.module_dir = self.project_root / "module"
        self.output_dir = self.project_root / "module_pyd"
        self.build_temp = self.project_root / "build_temp"
        
        self.files_to_compile = [
            "module/antiknockback.py",
            "module/reach.py",
            "module/hitbox.py",
            "module/zoom.py",
            "module/brightness.py",
            "module/speed.py",
            "module/coordinates.py",
            "module/autoclicker.py",
            "module/sprint.py",
            "module/streamprotect.py",
            "module/nohurtcam.py"
            "module/timechanger.py",
            "module/truesight.py"
            "module/fastitem.py",
            "module/systemtray.py"
        ]

    def clean(self):
        dirs_to_clean = [
            self.output_dir,
            self.build_temp,
            self.project_root / "build",
        ]
        
        for directory in dirs_to_clean:
            if directory.exists():
                shutil.rmtree(directory, ignore_errors=True)
        
        for root, dirs, files in os.walk(self.project_root):
            for file in files:
                if file.endswith(('.c', '.pyd', '.pyc', '.so', '.obj')):
                    file_path = Path(root) / file
                    try:
                        file_path.unlink()
                    except:
                        pass

    def setup_directories(self):
        self.output_dir.mkdir(exist_ok=True)
        self.build_temp.mkdir(exist_ok=True)

    def create_setup_py(self, source_file, module_name):
        setup_content = f"""
from setuptools import setup, Extension
from Cython.Build import cythonize
import sys

if sys.platform == 'win32':
    extra_compile_args = ['/O2', '/GL', '/favor:AMD64']
    extra_link_args = ['/LTCG']
else:
    extra_compile_args = ['-O3', '-march=native']
    extra_link_args = []

extensions = [
    Extension(
        name='{module_name}',
        sources=[r'{source_file}'],
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args,
    )
]

setup(
    name='{module_name}',
    ext_modules=cythonize(
        extensions,
        compiler_directives={{
            'language_level': 3,
            'embedsignature': False,
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
            'initializedcheck': False,
            'nonecheck': False,
            'overflowcheck': False,
            'always_allow_keywords': False,
            'c_string_type': 'bytes',
            'c_string_encoding': 'ascii',
        }},
        build_dir=r'{self.build_temp}',
        annotate=False,
    ),
)
"""
        setup_file = self.build_temp / f'setup_{module_name}.py'
        setup_file.write_text(setup_content, encoding='utf-8')
        return setup_file

    def compile_single_file(self, py_file):
        file_path = self.project_root / py_file
        
        if not file_path.exists():
            print(f"{py_file} - File not found")
            return False
        
        module_name = file_path.stem
        setup_file = self.create_setup_py(file_path, module_name)
        
        cmd = [
            sys.executable,
            str(setup_file),
            'build_ext',
            '--inplace',
        ]
        
        try:
            subprocess.run(
                cmd,
                cwd=str(self.project_root),
                check=True,
                capture_output=True,
                text=True
            )
            
            for root, dirs, files in os.walk(self.project_root):
                for file in files:
                    if file.startswith(module_name) and file.endswith('.pyd'):
                        src = Path(root) / file
                        dst = self.output_dir / file
                        shutil.move(str(src), str(dst))
                        print(f"{module_name}.pyd - Built successfully")
                        return True
            
            print(f"{module_name} - .pyd file not found")
            return False
            
        except subprocess.CalledProcessError:
            print(f"{module_name} - Compilation error")
            return False

    def compile_all(self):
        success_count = 0
        
        for py_file in self.files_to_compile:
            if self.compile_single_file(py_file):
                success_count += 1
        
        print(f"\nBuild completed: {success_count}/{len(self.files_to_compile)} modules")
        return success_count == len(self.files_to_compile)

    def create_module_init(self):
        init_content = """__all__ = [
    'antiknockback',
    'reach',
    'hitbox',
    'zoom',
    'brightness',
    'speed',
    'coordinates',
    'autoclicker',
    'sprint',
    'streamprotect',
    'nohurtcam',
    'timechanger',
    'truesight'
]
"""
        init_file = self.module_dir / '__init__.py'
        init_file.write_text(init_content, encoding='utf-8')

    def verify_dependencies(self):
        required = ['Cython', 'setuptools']
        
        for module in required:
            try:
                __import__(module)
            except ImportError:
                return False
        
        return True

    def generate_deployment_script(self):
        script_content = """@echo off
xcopy /Y module_pyd\\*.pyd module\\
pause
"""
        script_file = self.project_root / 'deploy_pyd.bat'
        script_file.write_text(script_content, encoding='utf-8')

    def build(self):
        if not self.verify_dependencies():
            return False
        
        self.clean()
        self.setup_directories()
        
        if not self.compile_all():
            return False
        
        self.create_module_init()
        self.generate_deployment_script()
        
        return True

def main():
    builder = PydBuilder()
    
    if not builder.project_root.exists():
        sys.exit(1)
    
    if not builder.module_dir.exists():
        sys.exit(1)
    
    if not builder.build():
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception:

        sys.exit(1)
