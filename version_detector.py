import subprocess
import json
import re
from subprocess import CREATE_NO_WINDOW

class MinecraftVersionDetector:
    SUPPORTED_VERSION_SERIES = {
        "1.21.12": {
            "speed_pattern": b'\xF3\x0F\x10\x01\xF3\x0F\x11\x44\x24\x20\xC6',
            "speed_original_length": 10,
           
            "hitbox_pattern": b'\xF3\x0F\x10\x79\x18\x49',
            "shadow_pattern": b'\xF3\x44\x0F\x11\x42\x10',
            "shadow_value_on": 0.6,
            "shadow_value_off": 0.6,
            "shadow_patch_length": 6,
           
            "series": "1.21.12"
        },
        "1.21.13": {
            "speed_pattern": b'\xF3\x0F\x10\x40\x7C\xF3\x0F\x11\x44\x24\x28',
            "speed_original_length": 11,
           
            "hitbox_pattern": b'\xF3\x0F\x10\x40\x18\x48\x83\xC4\x20',
            "shadow_pattern": b'\xF3\x44\x0F\x11\x42\x10',
            "shadow_value_on": 0.6,
            "shadow_value_off": 0.6,
            "shadow_patch_length": 6,
           
            "series": "1.21.13"
        }
    }
    
    @staticmethod
    def get_installed_version():
        powershell_command = (
            'Get-AppxPackage -Name "Microsoft.MinecraftUWP" | '
            'Select-Object Version | '
            'ConvertTo-Json'
        )
        
        try:
            result = subprocess.run(
                ["powershell", "-Command", powershell_command],
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8',
                timeout=10,
                creationflags=CREATE_NO_WINDOW
            )
            
            json_output = result.stdout.strip()
            
            if not json_output:
                return None
            
            packages = json.loads(json_output)
            if not isinstance(packages, list):
                packages = [packages]
            
            for package in packages:
                if 'Version' in package:
                    return package['Version']
            
            return None
            
        except subprocess.TimeoutExpired:
            print("PowerShell command timed out")
            return None
        except subprocess.CalledProcessError as e:
            print(f"PowerShell execution error: {e.stderr.strip()}")
            return None
        except json.JSONDecodeError:
            print("Invalid JSON output from PowerShell")
            return None
        except Exception as e:
            print(f"Error detecting Minecraft version: {e}")
            return None
    
    @staticmethod
    def parse_version(version_string):
        if not version_string:
            return None
        match = re.match(r'(\d+)\.(\d+)\.(\d+)', version_string)
        if match:
            major = match.group(1)
            minor = match.group(2)
            patch = match.group(3)[:2]
            return f"{major}.{minor}.{patch}"
        
        return None
    
    @classmethod
    def is_version_supported(cls, version_string):
        series_version = cls.parse_version(version_string)
        
        if not series_version:
            return False, None, None
        
        if series_version in cls.SUPPORTED_VERSION_SERIES:
            return True, series_version, cls.SUPPORTED_VERSION_SERIES[series_version]
        
        return False, series_version, None
    
    @classmethod
    def get_version_config(cls, version_string):
        _, _, config = cls.is_version_supported(version_string)
        return config
    
    @classmethod
    def check_compatibility(cls):
        installed = cls.get_installed_version()
        
        if not installed:
            return {
                'installed_version': None,
                'series_version': None,
                'supported': False,
                'config': None,
                'message': 'Minecraft Bedrock Edition not found'
            }
        
        supported, series_version, config = cls.is_version_supported(installed)
        
        display_version = installed
        version_match = re.match(r'(\d+\.\d+\.\d{3})', installed)
        if version_match:
            display_version = version_match.group(1)
        
        if supported:
            message = f"Compatible: {display_version}"
        else:
            supported_list = ', '.join([f"{s}0" for s in cls.SUPPORTED_VERSION_SERIES.keys()])
            message = f"Unsupported: {display_version}. Supported: {supported_list}"
        
        return {
            'installed_version': display_version,
            'series_version': series_version,
            'supported': supported,
            'config': config,
            'message': message
        }

if __name__ == "__main__":
    detector = MinecraftVersionDetector()
    
    print("Checking Minecraft version...")
    result = detector.check_compatibility()
    
    print(f"\nInstalled Version (Full): {result['installed_version']}")
    print(f"Series Version (X.XX.XX): {result['series_version']}")
    print(f"Supported: {result['supported']}")
    print(f"Message: {result['message']}")
    
    if result['config']:
        print(f"\nVersion Config:")
        print(f"  Series: {result['config']['series']}")
        print(f"  Speed Pattern Length: {len(result['config']['speed_pattern'])} bytes")
        print(f"  Hitbox Pattern Length: {len(result['config']['hitbox_pattern'])} bytes")
        print(f"  Shadow Value (ON): {result['config']['shadow_value_on']}")
        print(f"  Shadow Value (OFF): {result['config']['shadow_value_off']}")