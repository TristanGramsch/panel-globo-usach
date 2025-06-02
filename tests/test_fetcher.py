#!/usr/bin/env python3
"""
Test script for the Piloto file fetcher
"""

import sys
from fetch_piloto_files import PilotoFileFetcher

def test_basic_functionality():
    """Test basic functionality of the fetcher"""
    print("Testing Piloto File Fetcher...")
    
    fetcher = PilotoFileFetcher()
    
    # Test server health check
    print("1. Testing server health check...")
    if fetcher.check_server_health():
        print("   ✓ Server is accessible")
    else:
        print("   ✗ Server is not accessible")
        return False
    
    # Test directory listing
    print("2. Testing directory listing...")
    html_content = fetcher.get_directory_listing()
    if html_content:
        print(f"   ✓ Directory listing retrieved ({len(html_content)} characters)")
    else:
        print("   ✗ Failed to retrieve directory listing")
        return False
    
    # Test file parsing
    print("3. Testing file parsing...")
    files = fetcher.parse_piloto_files(html_content)
    if files:
        print(f"   ✓ Found {len(files)} Piloto files")
        print(f"   Sample files: {[f['filename'] for f in files[:3]]}")
    else:
        print("   ✗ No Piloto files found")
        return False
    
    # Test current month filtering
    print("4. Testing current month filtering...")
    current_files = fetcher.filter_current_month_files(files)
    print(f"   ✓ Found {len(current_files)} files for current month")
    if current_files:
        print(f"   Sample current month files: {[f['filename'] for f in current_files[:3]]}")
    
    # Test sensor summary
    print("5. Testing sensor summary...")
    sensors = fetcher.get_sensor_summary(current_files)
    print(f"   ✓ Detected sensors: {list(sensors.keys())}")
    print(f"   Files per sensor: {sensors}")
    
    print("\nAll basic tests passed!")
    return True

def test_single_download():
    """Test downloading a single file"""
    print("\nTesting single file download...")
    
    fetcher = PilotoFileFetcher()
    
    # Get current month files
    html_content = fetcher.get_directory_listing()
    if not html_content:
        print("   ✗ Could not get directory listing")
        return False
    
    files = fetcher.parse_piloto_files(html_content)
    current_files = fetcher.filter_current_month_files(files)
    
    if not current_files:
        print("   ✗ No current month files found to test download")
        return False
    
    # Try to download the first file
    test_file = current_files[0]
    filename = test_file['filename']
    
    print(f"   Testing download of: {filename}")
    
    if fetcher.download_file(filename):
        print(f"   ✓ Successfully downloaded {filename}")
        
        # Check local file info
        local_info = fetcher.get_local_file_info(filename)
        if local_info['exists']:
            print(f"   ✓ File exists locally ({local_info['size']} bytes)")
            if local_info['size'] == 0:
                print("   ⚠ Warning: File is empty")
            return True
        else:
            print("   ✗ File not found locally after download")
            return False
    else:
        print(f"   ✗ Failed to download {filename}")
        return False

def main():
    """Main test function"""
    print("="*60)
    print("PILOTO FILE FETCHER TEST SUITE")
    print("="*60)
    
    try:
        # Run basic functionality tests
        if not test_basic_functionality():
            print("\n❌ Basic functionality tests failed")
            sys.exit(1)
        
        # Run single download test
        if not test_single_download():
            print("\n❌ Download test failed")
            sys.exit(1)
        
        print("\n" + "="*60)
        print("🎉 ALL TESTS PASSED!")
        print("The fetcher is ready for use.")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 