"""
Jean Memory V2 - Setup Utilities
================================

Automatic dependency checking, installation, and environment setup utilities.
"""

import subprocess
import sys
import importlib
import pkg_resources
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import os

class DependencyManager:
    """Manages automatic dependency installation and verification"""
    
    def __init__(self, requirements_file: Optional[str] = None):
        """
        Initialize dependency manager
        
        Args:
            requirements_file: Path to requirements.txt file (auto-detected if None)
        """
        if requirements_file is None:
            # Use the working openmemory/api/requirements.txt for compatibility
            self.requirements_file = Path(__file__).parents[1] / "openmemory" / "api" / "requirements.txt"
            if not self.requirements_file.exists():
                # Fallback to local requirements.txt if openmemory not found
                self.requirements_file = Path(__file__).parent / "requirements.txt"
        else:
            self.requirements_file = Path(requirements_file)
        
        self.failed_imports = []
        self.missing_packages = []
        self.version_mismatches = []
    
    def parse_requirements(self) -> List[str]:
        """Parse requirements.txt file and return list of packages"""
        if not self.requirements_file.exists():
            raise FileNotFoundError(f"Requirements file not found: {self.requirements_file}")
        
        requirements = []
        with open(self.requirements_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    requirements.append(line)
        
        return requirements
    
    def check_package_installed(self, package_spec: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if a package is installed and meets version requirements
        
        Args:
            package_spec: Package specification (e.g., "mem0ai[graph]>=0.1.107")
            
        Returns:
            Tuple of (is_satisfied, installed_version, required_version)
        """
        try:
            # Parse package name and version requirement
            if '>=' in package_spec:
                package_name, version_spec = package_spec.split('>=')
                required_version = version_spec.split(',')[0]  # Handle version ranges
            elif '==' in package_spec:
                package_name, required_version = package_spec.split('==')
            elif '>' in package_spec:
                package_name, version_spec = package_spec.split('>')
                required_version = version_spec.split(',')[0]
            else:
                package_name = package_spec
                required_version = None
            
            # Handle extras like [graph]
            if '[' in package_name:
                package_name = package_name.split('[')[0]
            
            package_name = package_name.strip()
            
            # Check if package is installed
            try:
                installed_version = pkg_resources.get_distribution(package_name).version
                
                # If no version requirement, just check if installed
                if required_version is None:
                    return True, installed_version, None
                
                # Check version compatibility using pkg_resources
                requirement = pkg_resources.Requirement.parse(package_spec.replace('[graph]', ''))
                installed_dist = pkg_resources.get_distribution(package_name)
                
                is_satisfied = requirement.specifier.contains(installed_version)
                return is_satisfied, installed_version, required_version.strip()
                
            except pkg_resources.DistributionNotFound:
                return False, None, required_version.strip() if required_version else None
                
        except Exception as e:
            print(f"⚠️ Error checking package {package_spec}: {e}")
            return False, None, None
    
    def install_package(self, package_spec: str) -> bool:
        """
        Install a package using pip
        
        Args:
            package_spec: Package specification to install
            
        Returns:
            True if installation successful, False otherwise
        """
        try:
            print(f"📦 Installing {package_spec}...")
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', package_spec],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✅ Successfully installed {package_spec}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package_spec}: {e.stderr}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error installing {package_spec}: {e}")
            return False
    
    def check_all_dependencies(self) -> Dict[str, Dict]:
        """
        Check all dependencies from requirements file
        
        Returns:
            Dictionary with package status information
        """
        requirements = self.parse_requirements()
        status = {}
        
        print(f"🔍 Checking {len(requirements)} dependencies...")
        
        for package_spec in requirements:
            is_satisfied, installed_version, required_version = self.check_package_installed(package_spec)
            
            package_name = package_spec.split('>=')[0].split('==')[0].split('>')[0].split('[')[0].strip()
            
            status[package_name] = {
                'spec': package_spec,
                'satisfied': is_satisfied,
                'installed_version': installed_version,
                'required_version': required_version,
                'status': 'OK' if is_satisfied else ('MISSING' if installed_version is None else 'VERSION_MISMATCH')
            }
            
            if is_satisfied:
                print(f"   ✅ {package_name}: {installed_version}")
            elif installed_version is None:
                print(f"   ❌ {package_name}: NOT INSTALLED (required: {required_version})")
                self.missing_packages.append(package_spec)
            else:
                print(f"   ⚠️  {package_name}: {installed_version} (required: {required_version})")
                self.version_mismatches.append(package_spec)
        
        return status
    
    def install_missing_dependencies(self, auto_install: bool = False) -> bool:
        """
        Install missing dependencies
        
        Args:
            auto_install: If True, install without prompting
            
        Returns:
            True if all installations successful
        """
        if not self.missing_packages and not self.version_mismatches:
            print("✅ All dependencies satisfied!")
            return True
        
        all_missing = self.missing_packages + self.version_mismatches
        
        if not auto_install:
            print(f"\n📦 Found {len(all_missing)} packages that need installation:")
            for pkg in all_missing:
                print(f"   • {pkg}")
            
            response = input(f"\nInstall missing dependencies? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                print("❌ Installation cancelled by user")
                return False
        
        print(f"\n📦 Installing {len(all_missing)} packages...")
        success_count = 0
        
        for package_spec in all_missing:
            if self.install_package(package_spec):
                success_count += 1
            else:
                print(f"⚠️ Failed to install {package_spec}")
        
        if success_count == len(all_missing):
            print(f"\n🎉 Successfully installed all {success_count} packages!")
            return True
        else:
            print(f"\n⚠️ Installed {success_count}/{len(all_missing)} packages successfully")
            return False
    
    def setup_environment(self, auto_install: bool = False) -> bool:
        """
        Complete environment setup: check dependencies and install if needed
        
        Args:
            auto_install: If True, install missing packages without prompting
            
        Returns:
            True if environment is ready, False otherwise
        """
        print("🚀 Jean Memory V2 - Environment Setup")
        print("=" * 50)
        
        try:
            # Check all dependencies
            status = self.check_all_dependencies()
            
            # Install missing dependencies if any
            if self.missing_packages or self.version_mismatches:
                success = self.install_missing_dependencies(auto_install=auto_install)
                if not success:
                    return False
                
                # Re-check after installation
                print("\n🔍 Re-checking dependencies after installation...")
                self.missing_packages.clear()
                self.version_mismatches.clear()
                status = self.check_all_dependencies()
            
            # Final validation
            failed_packages = [
                name for name, info in status.items() 
                if not info['satisfied']
            ]
            
            if failed_packages:
                print(f"\n❌ Environment setup failed. Unresolved packages: {failed_packages}")
                return False
            else:
                print(f"\n✅ Environment setup complete! All {len(status)} dependencies satisfied.")
                return True
                
        except Exception as e:
            print(f"❌ Environment setup failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def setup_jean_memory_v2_environment(auto_install: bool = False) -> bool:
    """
    Convenient function to set up Jean Memory V2 environment
    
    Args:
        auto_install: If True, automatically install missing dependencies
        
    Returns:
        True if environment is ready, False otherwise
    """
    manager = DependencyManager()
    return manager.setup_environment(auto_install=auto_install)


def check_core_imports() -> bool:
    """
    Check if core Jean Memory V2 imports work after dependency installation
    
    Returns:
        True if all core imports successful, False otherwise
    """
    print("\n🧪 Testing core imports...")
    
    core_imports = [
        ('mem0', 'Memory'),
        ('graphiti', 'Graphiti'),
        ('openai', 'OpenAI'),
        ('qdrant_client', 'QdrantClient'),
        ('neo4j', 'GraphDatabase'),
        ('google.generativeai', None),
    ]
    
    failed_imports = []
    
    for module_name, class_name in core_imports:
        try:
            module = importlib.import_module(module_name)
            if class_name:
                getattr(module, class_name)
            print(f"   ✅ {module_name}")
        except ImportError as e:
            print(f"   ❌ {module_name}: {e}")
            failed_imports.append(module_name)
        except AttributeError as e:
            print(f"   ⚠️ {module_name}: {e}")
            failed_imports.append(f"{module_name}.{class_name}")
    
    if failed_imports:
        print(f"\n❌ Failed imports: {failed_imports}")
        return False
    else:
        print(f"\n✅ All core imports successful!")
        return True


if __name__ == "__main__":
    """CLI usage for dependency setup"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Jean Memory V2 Environment Setup")
    parser.add_argument('--auto-install', action='store_true', 
                       help='Automatically install missing dependencies')
    parser.add_argument('--check-only', action='store_true',
                       help='Only check dependencies, do not install')
    
    args = parser.parse_args()
    
    manager = DependencyManager()
    
    if args.check_only:
        status = manager.check_all_dependencies()
        check_core_imports()
    else:
        success = manager.setup_environment(auto_install=args.auto_install)
        if success:
            check_core_imports()
        sys.exit(0 if success else 1) 