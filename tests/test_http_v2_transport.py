#!/usr/bin/env python3
"""
Test script for HTTP v2 Transport Endpoints
This validates that the new direct backend routing works correctly.
"""
import requests
import json
import time

# Test configurations
LOCAL_BASE_URL = "http://localhost:8765"
PROD_BASE_URL = "https://jean-memory-api-virginia.onrender.com"

# Test user (use a test UUID format)
TEST_USER_ID = "test-user-12345"
TEST_CLIENT = "claude"

def test_http_v2_initialize(base_url: str):
    """Test the initialize method via HTTP v2 transport"""
    print(f"Testing HTTP v2 initialize on {base_url}...")
    
    url = f"{base_url}/mcp/v2/{TEST_CLIENT}/{TEST_USER_ID}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"},
        "id": "init-test"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("result", {}).get("serverInfo", {}).get("name") == "Jean Memory":
                print("✅ HTTP v2 initialize successful")
                print(f"   Protocol Version: {result['result'].get('protocolVersion')}")
                print(f"   Server Info: {result['result']['serverInfo']}")
                return True
            else:
                print(f"❌ Unexpected initialize response: {result}")
                return False
        else:
            print(f"❌ Initialize failed with status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Initialize request failed: {e}")
        return False

def test_http_v2_tools_list(base_url: str):
    """Test the tools/list method via HTTP v2 transport"""
    print(f"Testing HTTP v2 tools/list on {base_url}...")
    
    url = f"{base_url}/mcp/v2/{TEST_CLIENT}/{TEST_USER_ID}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": "tools-test"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            tools = result.get("result", {}).get("tools", [])
            if tools:
                print(f"✅ HTTP v2 tools/list successful - Found {len(tools)} tools")
                for tool in tools[:3]:  # Show first 3 tools
                    print(f"   - {tool.get('name')}: {tool.get('description', '')[:50]}...")
                return True
            else:
                print(f"❌ No tools returned: {result}")
                return False
        else:
            print(f"❌ Tools/list failed with status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Tools/list request failed: {e}")
        return False

def test_http_v2_vs_sse_performance(base_url: str):
    """Compare HTTP v2 vs SSE performance"""
    print(f"Testing HTTP v2 vs SSE performance on {base_url}...")
    
    # Test HTTP v2 performance
    http_v2_url = f"{base_url}/mcp/v2/{TEST_CLIENT}/{TEST_USER_ID}"
    sse_messages_url = f"{base_url}/mcp/{TEST_CLIENT}/messages/{TEST_USER_ID}"
    
    headers = {'Content-Type': 'application/json'}
    test_data = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": "perf-test"
    }
    
    # Test HTTP v2 speed
    http_v2_times = []
    for i in range(3):
        start_time = time.time()
        try:
            response = requests.post(http_v2_url, headers=headers, json=test_data, timeout=10)
            if response.status_code == 200:
                http_v2_times.append(time.time() - start_time)
        except:
            pass
    
    # Test SSE speed (messages endpoint without SSE connection - direct HTTP)
    sse_headers = {**headers, 'x-user-id': TEST_USER_ID, 'x-client-name': TEST_CLIENT}
    sse_times = []
    for i in range(3):
        start_time = time.time()
        try:
            response = requests.post(sse_messages_url, headers=sse_headers, json=test_data, timeout=10)
            if response.status_code in [200, 204]:  # SSE might return 204
                sse_times.append(time.time() - start_time)
        except:
            pass
    
    if http_v2_times and sse_times:
        http_v2_avg = sum(http_v2_times) / len(http_v2_times)
        sse_avg = sum(sse_times) / len(sse_times)
        improvement = ((sse_avg - http_v2_avg) / sse_avg) * 100
        
        print(f"📊 Performance Comparison:")
        print(f"   HTTP v2 average: {http_v2_avg:.3f}s")
        print(f"   SSE average: {sse_avg:.3f}s") 
        print(f"   Performance improvement: {improvement:.1f}%")
        
        if improvement > 0:
            print("✅ HTTP v2 is faster than SSE transport")
            return True
        else:
            print("⚠️ HTTP v2 is not significantly faster (may be due to test conditions)")
            return False
    else:
        print("❌ Could not complete performance comparison")
        return False

def test_error_handling(base_url: str):
    """Test error handling in HTTP v2 transport"""
    print(f"Testing HTTP v2 error handling on {base_url}...")
    
    url = f"{base_url}/mcp/v2/{TEST_CLIENT}/{TEST_USER_ID}"
    headers = {'Content-Type': 'application/json'}
    
    # Test invalid method
    data = {
        "jsonrpc": "2.0",
        "method": "invalid_method",
        "params": {},
        "id": "error-test"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 404:
            result = response.json()
            if "not found" in result.get("error", "").lower():
                print("✅ HTTP v2 error handling works correctly")
                return True
        
        print(f"❌ Unexpected error response: {response.status_code} - {response.text}")
        return False
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error handling test failed: {e}")
        return False

def main():
    """Run all HTTP v2 transport tests"""
    print("🚀 HTTP v2 Transport Testing Suite")
    print("=" * 50)
    
    # Test environments
    environments = [
        ("Local Development", LOCAL_BASE_URL),
        ("Production", PROD_BASE_URL)
    ]
    
    for env_name, base_url in environments:
        print(f"\n🔍 Testing {env_name} Environment ({base_url})")
        print("-" * 30)
        
        # Run all tests
        tests = [
            test_http_v2_initialize,
            test_http_v2_tools_list,
            test_http_v2_vs_sse_performance,
            test_error_handling
        ]
        
        results = []
        for test_func in tests:
            try:
                result = test_func(base_url)
                results.append(result)
            except Exception as e:
                print(f"❌ Test {test_func.__name__} crashed: {e}")
                results.append(False)
        
        # Summary
        passed = sum(results)
        total = len(results)
        print(f"\n📊 {env_name} Results: {passed}/{total} tests passed")
        
        if passed == total:
            print(f"✅ All tests passed for {env_name}!")
        else:
            print(f"⚠️ Some tests failed for {env_name}")
    
    print("\n" + "=" * 50)
    print("🏁 HTTP v2 Transport Testing Complete")
    print("\nNext Steps:")
    print("1. If tests pass: Ready for Phase 2 (Dashboard Updates)")
    print("2. If tests fail: Debug and fix issues before proceeding")
    print("3. Monitor performance improvements in production")

if __name__ == "__main__":
    main() 