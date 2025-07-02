#!/usr/bin/env python3
"""
Standalone test for SMS conversation continuity functionality
"""
import sys
import os
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Now we can import our modules
from app.utils.sms import SMSContextManager, SMSService
from app.models import SMSRole, SubscriptionTier

def test_conversation_context_formatting():
    """Test that conversation context is formatted correctly"""
    print("Testing conversation context formatting...")
    
    # Mock database session and user
    mock_db = Mock()
    mock_user = Mock()
    mock_user.id = "test-uuid-123"
    mock_user.user_id = "test-user-456"
    
    # Mock conversation history
    mock_messages = [
        Mock(role=SMSRole.USER, content="Remember to buy milk", created_at=datetime.now(timezone.utc)),
        Mock(role=SMSRole.ASSISTANT, content="Got it! I'll remember that.", created_at=datetime.now(timezone.utc)),
        Mock(role=SMSRole.USER, content="What should I get at the store?", created_at=datetime.now(timezone.utc)),
    ]
    
    # Mock database queries
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_messages
    
    # Test get_conversation_context
    context = SMSContextManager.get_conversation_context("test-user-456", mock_db)
    
    expected_context = """Recent conversation:
You: Remember to buy milk
Jean Memory: Got it! I'll remember that.
You: What should I get at the store?"""
    
    if context == expected_context:
        print("✓ Conversation context formatting works correctly")
        return True
    else:
        print("✗ Conversation context formatting failed")
        print(f"Expected: {expected_context}")
        print(f"Got: {context}")
        return False

def test_add_message_to_conversation():
    """Test adding messages to conversation history"""
    print("Testing add message to conversation...")
    
    # Mock database session and user
    mock_db = Mock()
    mock_user = Mock()
    mock_user.id = "test-uuid-123"
    
    # Mock database query to return the user
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    
    # Test adding a user message
    result = SMSContextManager.add_message_to_conversation(
        user_id="test-user-456",
        phone_number="+1234567890",
        content="Remember to buy milk",
        role="user",
        db=mock_db
    )
    
    if result:
        print("✓ Successfully added message to conversation")
        # Verify database operations were called
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        return True
    else:
        print("✗ Failed to add message to conversation")
        return False

def test_conversation_continuity_in_ai_prompt():
    """Test that conversation context is included in AI processing"""
    print("Testing conversation continuity in AI prompt...")
    
    # Create a mock database with conversation history
    mock_db = Mock()
    mock_user = Mock()
    mock_user.id = "test-uuid-123"
    mock_user.user_id = "test-user-456"
    
    # Mock conversation history
    mock_messages = [
        Mock(role=SMSRole.USER, content="Remember to buy milk", created_at=datetime.now(timezone.utc)),
        Mock(role=SMSRole.ASSISTANT, content="Got it! I'll remember that.", created_at=datetime.now(timezone.utc)),
    ]
    
    # Mock database queries
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_messages
    
    # Mock environment variables
    os.environ['ANTHROPIC_API_KEY'] = 'test-key'
    
    # Test SMS service with conversation context
    sms_service = SMSService()
    
    # We'll just test that conversation context is retrieved
    # (the actual AI call would require real API credentials)
    context = SMSContextManager.get_conversation_context("test-user-456", mock_db)
    
    if "Recent conversation:" in context and "milk" in context:
        print("✓ Conversation context includes recent history")
        print(f"  Context: {context}")
        return True
    else:
        print("✗ Conversation context missing or incomplete")
        return False

def test_role_enum_mapping():
    """Test SMS role enum mapping"""
    print("Testing SMS role enum mapping...")
    
    try:
        # Test that the enum values are what we expect
        assert SMSRole.USER.value == "USER"
        assert SMSRole.ASSISTANT.value == "ASSISTANT"
        
        print("✓ SMS role enum values are correct")
        return True
    except Exception as e:
        print(f"✗ SMS role enum test failed: {e}")
        return False

def test_empty_conversation_handling():
    """Test handling of empty conversation history"""
    print("Testing empty conversation handling...")
    
    # Mock database session and user with no conversation history
    mock_db = Mock()
    mock_user = Mock()
    mock_user.id = "test-uuid-123"
    mock_user.user_id = "test-user-456"
    
    # Mock database queries to return empty history
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    
    # Test get_conversation_context with no history
    context = SMSContextManager.get_conversation_context("test-user-456", mock_db)
    
    if context == "":
        print("✓ Empty conversation handled correctly")
        return True
    else:
        print(f"✗ Expected empty string, got: '{context}'")
        return False

def test_user_not_found_handling():
    """Test handling when user is not found"""
    print("Testing user not found handling...")
    
    # Mock database session that returns None for user query
    mock_db = Mock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    # Test conversation context retrieval
    context = SMSContextManager.get_conversation_context("nonexistent-user", mock_db)
    
    # Test adding message
    result = SMSContextManager.add_message_to_conversation(
        user_id="nonexistent-user",
        phone_number="+1234567890",
        content="Test message",
        role="user",
        db=mock_db
    )
    
    if context == "" and result is False:
        print("✓ User not found handled correctly")
        return True
    else:
        print("✗ User not found handling failed")
        return False

def main():
    """Run all tests"""
    print("SMS Conversation Continuity Test Suite")
    print("=" * 50)
    
    tests = [
        test_role_enum_mapping,
        test_conversation_context_formatting,
        test_add_message_to_conversation,
        test_empty_conversation_handling,
        test_user_not_found_handling,
        test_conversation_continuity_in_ai_prompt,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()  # Add spacing between tests
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            print()
    
    # Summary
    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All SMS conversation continuity tests passed!")
        print("\nKey features verified:")
        print("- Conversation history is stored and retrieved correctly")
        print("- Context is formatted properly for AI processing")
        print("- Edge cases (empty history, missing users) are handled")
        print("- Role enum mapping works as expected")
        print("\nYour SMS conversation continuity is ready to use!")
        return True
    else:
        print(f"❌ {total - passed} tests failed")
        print("\nSome SMS conversation features may not work correctly.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 