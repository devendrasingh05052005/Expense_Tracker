"""
Strict AI Expense Assistant
Mandatory fields rule with context memory and multi-missing handling
"""

import json
import re
import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from groq import Groq
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from .models import Expense, CATEGORY_CHOICES


class StrictExpenseAssistant:
    """AI assistant with mandatory fields rule and context memory"""
    
    def __init__(self, groq_api_key: str):
        self.client = Groq(api_key=groq_api_key)
        
        # Smart category mapping
        self.category_map = {
            'chai': 'food', 'tea': 'food', 'coffee': 'food', 'pani puri': 'food',
            'samosa': 'food', 'vada pav': 'food', 'dosa': 'food', 'idli': 'food',
            'khana': 'food', 'food': 'food', 'lunch': 'food', 'dinner': 'food',
            'breakfast': 'food', 'snacks': 'food', 'meal': 'food', 'pizza': 'food',
            'burger': 'food', 'thali': 'food', 'biryani': 'food', 'namkeen': 'food',
            
            'uber': 'travel', 'ola': 'travel', 'taxi': 'travel', 'auto': 'travel',
            'bus': 'travel', 'metro': 'travel', 'train': 'travel', 'rickshaw': 'travel',
            'petrol': 'travel', 'diesel': 'travel', 'cng': 'travel', 'travel': 'travel',
            'cab': 'travel', 'flight': 'travel', 'ticket': 'travel',
            
            'clothes': 'shopping', 'shirt': 'shopping', 'pant': 'shopping',
            'jeans': 'shopping', 'shoes': 'shopping', 'shopping': 'shopping',
            'market': 'shopping', 'mall': 'shopping', 'buy': 'shopping',
            'amazon': 'shopping', 'flipkart': 'shopping', 'online': 'shopping',
            'purchase': 'shopping', 'kapde': 'shopping',
            
            'electricity': 'bills', 'water': 'bills', 'gas': 'bills',
            'phone': 'bills', 'internet': 'bills', 'rent': 'bills',
            'bill': 'bills', 'recharge': 'bills', 'emi': 'bills',
            
            'medicine': 'health', 'doctor': 'health', 'hospital': 'health',
            'health': 'health', 'dawai': 'health', 'checkup': 'health',
            'medical': 'health',
            
            'movie': 'entertainment', 'cinema': 'entertainment', 'netflix': 'entertainment',
            'prime': 'entertainment', 'game': 'entertainment', 'entertainment': 'entertainment',
            'ott': 'entertainment', 'subscription': 'entertainment'
        }
        
        self.valid_categories = [choice[0] for choice in CATEGORY_CHOICES]
    
    def process_request(self, user_input: str, user, request=None) -> Dict[str, Any]:
        """Process user input with mandatory fields rule"""
        
        try:
            # Validate user
            if not user or not user.is_authenticated:
                return self._create_response(
                    intent="none",
                    response="Please log in first to use the expense tracking feature."
                )
            
            # Use session for context memory
            session = request.session if request else {}
            
            # Step 1: Get pending data from session
            pending = session.get('pending', {})
            
            # Step 2: Extract ALL entities from user input
            amount = self._extract_amount(user_input)
            category = self._extract_category(user_input)
            date = self._extract_date_smart(user_input)
            
            # Step 3: Partial data merge - update only if present
            if amount:
                pending["amount"] = amount
            if category:
                pending["category"] = category
            if date:
                pending["date"] = date
            
            # Store updated pending data in session
            session["pending"] = pending
            
            print(f"[BACKEND] Pending data after merge: {pending}")
            
            # Step 4: Check completion - if all fields present, execute ADD
            if all([pending.get("amount"), pending.get("category"), pending.get("date")]):
                result = self._add_expense_to_db(pending, user)
                # Clear pending data after successful add
                session["pending"] = {}
                return result
            
            # Step 5: Determine what's missing and ask accordingly
            intent, response = self._determine_intent_and_response(pending, user_input)
            
            return self._create_response(
                intent=intent,
                amount=pending.get('amount'),
                category=pending.get('category'),
                date=pending.get('date'),
                response=response
            )
                
        except Exception as e:
            print(f"[BACKEND] Error: {e}")
            import traceback
            traceback.print_exc()
            return self._create_response(
                intent="none",
                response="Let me try that again. What would you like to do with your expenses?"
            )
    
    def _determine_intent_and_response(self, pending: Dict[str, Any], user_input: str) -> tuple:
        """Determine intent and response based on missing fields"""
        amount = pending.get('amount')
        category = pending.get('category')
        date = pending.get('date')
        
        # Check if all mandatory fields are present
        if amount and category and date:
            return 'add', f"Added {amount} for {category} on {date}."
        
        # Check what's missing
        missing_fields = []
        if not amount:
            missing_fields.append('amount')
        if not category:
            missing_fields.append('category')
        if not date:
            missing_fields.append('date')
        
        # If no amount yet, ask for amount first
        if not amount:
            return 'ask_amount', "How much did you spend?"
        
        # Multi-missing handling
        if len(missing_fields) > 1:
            if 'category' in missing_fields and 'date' in missing_fields:
                return 'ask_both', "Please tell me the category and date for this expense."
            elif 'category' in missing_fields and 'amount' not in missing_fields:
                return 'ask_category', "Which category does this belong to? (food, travel, shopping, etc.)"
            elif 'date' in missing_fields and 'amount' not in missing_fields:
                return 'ask_date', "On which date should I add this expense?"
        
        # Single missing field
        if not category:
            return 'ask_category', "Which category does this belong to? (food, travel, shopping, etc.)"
        elif not date:
            return 'ask_date', "On which date should I add this expense?"
        
        # Default fallback
        return 'add', f"Added {amount} for {category} on {date}."
    
    def _extract_amount(self, user_input: str) -> Optional[float]:
        """Extract amount from user input"""
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:rs|rpm|rupees?|bucks?|\$)',
            r'(?:rs|rpm|rupees?|bucks?|\$)\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:ka|ke|ki)',
            r'(?:spent|paid|kharch|kharch kiya|daala|laga|pee li)\s+(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:ka|ke|ki)\s+(?:kharch|expense)',
            r'^(\d+(?:\.\d+)?)$',  # Just numbers
        ]
        
        for pattern in patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None
    
    def _extract_category(self, user_input: str) -> Optional[str]:
        """Extract category from user input with smart mapping"""
        user_input_lower = user_input.lower()
        
        # Check Hinglish mappings first
        for hinglish_word, mapped_category in self.category_map.items():
            if hinglish_word in user_input_lower:
                return mapped_category
        
        # Check direct category names
        for category in self.valid_categories:
            if category in user_input_lower:
                return category
        
        return None
    
    def _extract_date_smart(self, user_input: str) -> Optional[str]:
        """Extract date from user input with safe parsing"""
        user_input_lower = user_input.lower()
        
        # Rule 1: Only parse if date keywords are present
        date_keywords = [
            "today", "yesterday", "tomorrow", "aaj", "kal",
            "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
            "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
            "2024", "2025", "2026", "2027", "2028", "2029", "2030"
        ]
        
        def has_date(text):
            return any(word in text for word in date_keywords)
        
        # Simple date mapping
        date_map = {
            'today': 'today', 'aaj': 'today',
            'yesterday': 'yesterday', 'kal': 'yesterday',
            'tomorrow': 'tomorrow',
        }
        
        for hinglish, english in date_map.items():
            if hinglish in user_input_lower:
                return english
        
        # Rule 2: Extract amount first and remove it from text
        amount_match = re.search(r'\b\d+(?:\.\d+)?\b', user_input)
        clean_text = user_input
        if amount_match:
            amount_str = amount_match.group()
            clean_text = clean_text.replace(amount_str, '')
        
        # Rule 3: Only parse date if date keywords are present
        if not has_date(clean_text.lower()):
            return None
        
        # Check for date patterns (YYYY-MM-DD or DD-MM-YYYY)
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{2}-\d{2}-\d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, clean_text)
            if match:
                date_str = match.group(1)
                # Convert to standard format
                try:
                    if '-' in date_str and len(date_str.split('-')[0]) == 4:
                        return date_str  # Already in YYYY-MM-DD format
                    elif '-' in date_str:
                        # Convert DD-MM-YYYY to YYYY-MM-DD
                        parts = date_str.split('-')
                        return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    elif '/' in date_str:
                        # Convert MM/DD/YYYY to YYYY-MM-DD
                        parts = date_str.split('/')
                        return f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                except:
                    continue
        
        # Rule 4: Safe date parsing with dateutil only if date keywords present
        try:
            from dateutil import parser
            parsed_date = parser.parse(clean_text, fuzzy=True)
            # Validate year is reasonable (not 500)
            year = parsed_date.year
            if year < 1900 or year > 2100:
                return None
            # Convert to YYYY-MM-DD format
            return parsed_date.strftime('%Y-%m-%d')
        except:
            pass
        
        # Rule 5: Handle special cases like "6jan2026", "6 january 2026"
        for month_abbr, month_num in {
            'jan': '01', 'january': '01',
            'feb': '02', 'february': '02',
            'mar': '03', 'march': '03',
            'apr': '04', 'april': '04',
            'may': '05',
            'jun': '06', 'june': '06',
            'jul': '07', 'july': '07',
            'aug': '08', 'august': '08',
            'sep': '09', 'september': '09',
            'oct': '10', 'october': '10',
            'nov': '11', 'november': '11',
            'dec': '12', 'december': '12',
        }.items():
            # Pattern for "6jan2026" or "6 january 2026"
            pattern = rf'(\d{{1,2}})\s*{month_abbr}\s*(\d{{4}})'
            match = re.search(pattern, clean_text.lower())
            if match:
                try:
                    day = match.group(1).zfill(2)
                    year = match.group(2)
                    # Validate year is reasonable
                    if int(year) < 1900 or int(year) > 2100:
                        continue
                    return f"{year}-{month_num}-{day}"
                except:
                    continue
        
        return None
    
    def _add_expense_to_db(self, pending: Dict[str, Any], user) -> Dict[str, Any]:
        """Add expense to database with all mandatory fields"""
        try:
            from django.utils import timezone
            from .models import Expense
            
            amount = pending['amount']
            category = pending['category']
            date_str = pending['date']
            
            # Parse date
            expense_date = self._parse_date_to_date(date_str)
            
            # Create expense in database
            expense = Expense.objects.create(
                user=user,
                amount=Decimal(str(amount)),
                category=category,
                title=f'{category} expense',
                date=expense_date
            )
            
            response = f"Added {amount} for {category} on {date_str}."
            
        except Exception as e:
            response = f"Adding {amount} for {category} on {date_str}."
        
        return self._create_response(
            intent="add",
            amount=amount,
            category=category,
            date=date_str,
            response=response
        )
    
    def _parse_date_to_date(self, date_str: str) -> datetime.date:
        """Parse date string to actual date object"""
        today = timezone.now().date()
        
        if date_str == 'today':
            return today
        elif date_str == 'yesterday':
            return today - datetime.timedelta(days=1)
        elif date_str == 'tomorrow':
            return today + datetime.timedelta(days=1)
        else:
            # Try to parse as YYYY-MM-DD
            try:
                return datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                return today
    
    def _create_response(self, intent: str, amount: float = None, category: str = None, 
                        date: str = None, response: str = None) -> Dict[str, Any]:
        """Create standardized JSON response"""
        
        return {
            "intent": intent,
            "amount": amount,
            "category": category,
            "date": date,
            "response": response
        }
