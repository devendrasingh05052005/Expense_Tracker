import os
import re
import logging
from typing import Annotated, TypedDict, List, Optional
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from django.db.models import Sum, Q, Count, Avg
from django.utils import timezone
from decimal import Decimal
from .models import Expense

logger = logging.getLogger(__name__)

# --- Agent Caching for Performance ---
_AGENT_CACHE = None

def get_cached_agent(api_key: str):
    """Get cached agent to avoid recompiling on every request"""
    global _AGENT_CACHE
    if _AGENT_CACHE is None:
        logger.info("🔧 Creating new agent (cache miss)")
        _AGENT_CACHE = get_expense_agent(api_key)
    return _AGENT_CACHE

def clear_agent_cache():
    """Clear the cached agent - call when tool definitions change"""
    global _AGENT_CACHE
    _AGENT_CACHE = None
    logger.warning("🔄 Agent cache cleared - tools will be rebuilt")

# --- 1. State Definition ---
class AgentState(TypedDict):
    """State for the LangGraph agent"""
    # This keeps track of the conversation history
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: int

# --- 2. Tool Definitions (@tool) ---
# These are the actual "skills" your agent has.

@tool
def query_expenses(user_id: int, query_str: Optional[str] = "", category: Optional[str] = None, period: Optional[str] = None):
    """
    Search for expenses with flexible filtering.
    
    Args:
        user_id: The ID of the user (REQUIRED)
        query_str: Search string (Optional, default is empty string)
        category: Category string (Optional, like 'food', 'travel', 'shopping')
        period: Time period (Optional, like 'today', 'this_week', 'this_month', 'last_month')
    
    Returns:
        Formatted string of matching expenses
    """
    from datetime import timedelta
    
    expenses = Expense.objects.filter(user_id=user_id)
    
    # Apply filters with proper validation
    if query_str and query_str.strip():
        expenses = expenses.filter(Q(title__icontains=query_str) | Q(category__icontains=query_str))
    
    if category and category.strip():
        expenses = expenses.filter(category=category.lower())
    
    if period and period.strip():
        today = timezone.now().date()
        if period == 'today':
            expenses = expenses.filter(date=today)
        elif period == 'this_week':
            start = today - timedelta(days=today.weekday())
            expenses = expenses.filter(date__gte=start, date__lte=today)
        elif period == 'this_month':
            start = today.replace(day=1)
            expenses = expenses.filter(date__gte=start, date__lte=today)
        elif period == 'last_month':
            if today.month == 1:
                start = today.replace(year=today.year-1, month=12, day=1)
                end = today.replace(year=today.year-1, month=12, day=31)
            else:
                start = today.replace(month=today.month-1, day=1)
                end = today.replace(day=1) - timedelta(days=1)
            expenses = expenses.filter(date__gte=start, date__lte=end)
    
    # Format results
    results = []
    for e in expenses.order_by('-date')[:10]:  # Limit for context window safety
        results.append(f"{e.date.strftime('%Y-%m-%d')}: {e.title} - ${e.amount} ({e.category})")
    
    return "\n".join(results) if results else "No expenses found."

@tool
def get_spending_stats(user_id: int, period: Optional[str] = "this_month", category: Optional[str] = None):
    """
    Calculate financial statistics for a user.
    
    Args:
        user_id: Unique user identifier (REQUIRED)
        period: Timeframe to analyze (today, this_week, this_month, last_month). Default is 'this_month'
        category: Specific category for stats (Optional, like 'food', 'travel')
    
    Returns:
        Formatted spending statistics
    """
    from datetime import timedelta
    
    # Fallback for missing period
    p = period if period and period.strip() else "this_month"
    
    expenses = Expense.objects.filter(user_id=user_id)
    
    # Apply period filter
    today = timezone.now().date()
    if p == 'today':
        expenses = expenses.filter(date=today)
    elif p == 'this_week':
        start = today - timedelta(days=today.weekday())
        expenses = expenses.filter(date__gte=start, date__lte=today)
    elif p == 'this_month':
        start = today.replace(day=1)
        expenses = expenses.filter(date__gte=start, date__lte=today)
    elif p == 'last_month':
            if today.month == 1:
                start = today.replace(year=today.year-1, month=12, day=1)
                end = today.replace(year=today.year-1, month=12, day=31)
            else:
                start = today.replace(month=today.month-1, day=1)
                end = today.replace(day=1) - timedelta(days=1)
            expenses = expenses.filter(date__gte=start, date__lte=end)
    
    # Calculate statistics
    total = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    count = expenses.count()
    avg = expenses.aggregate(Avg('amount'))['amount__avg'] or 0
    
    # Category breakdown
    category_stats = expenses.values('category').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    return {
        'total': float(total),
        'count': count,
        'average': float(avg),
        'period': period,
        'category_breakdown': list(category_stats)
    }

@tool
def add_expense(user_id: int, amount: float, category: str, date_str: Optional[str] = None) -> str:
    """
    Add a new expense to the database.
    
    Args:
        user_id: ID of the user (REQUIRED)
        amount: Amount spent in rupees (REQUIRED)
        category: Category of expense - MUST be one of: food, travel, shopping, bills, health, entertainment, others (REQUIRED)
        date_str: Date in DD-MM-YYYY format (e.g., '05-05-2002'), or leave empty for today
    
    Returns:
        Success message with expense details
    """
    try:
        # Parse date
        if date_str and date_str.strip():
            try:
                # Try DD-MM-YYYY format
                expense_date = timezone.datetime.strptime(date_str.strip(), '%d-%m-%Y').date()
            except:
                try:
                    # Try YYYY-MM-DD format
                    expense_date = timezone.datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
                except:
                    # Default to today if parsing fails
                    expense_date = timezone.now().date()
        else:
            # Use today's date if not provided
            expense_date = timezone.now().date()
        
        # Description is just the category name
        desc = f"{category} expense"
        
        # Create expense
        expense = Expense.objects.create(
            user_id=user_id,
            amount=Decimal(str(amount)),
            category=category.lower(),
            title=desc,
            date=expense_date
        )
        
        return f"Successfully added expense: ₹{amount} for {category} on {expense_date.strftime('%d-%m-%Y')}"
        
    except Exception as e:
        return f"Error adding expense: {str(e)}"

@tool
def delete_expense(user_id: int, expense_id: Optional[int] = None, delete_last: bool = False):
    """
    Delete an expense. Choose ONE deletion method: either expense_id OR delete_last=true.
    NOTE: Cannot delete all expenses at once. Only deletes one expense per request.
    
    Args:
        user_id: The ID of the user (REQUIRED)
        expense_id: Specific expense ID to delete (set to 0 to skip, use delete_last instead)
        delete_last: Set to true to delete the most recent expense (use this OR expense_id, not both)
    
    Returns:
        Success message with deleted expense details, or error if deletion failed
    """
    try:
        # Agar user 'all' bole toh mana kar do system prompt ke through, 
        # par tool ko crash mat hone do.
        if delete_last:
            expense = Expense.objects.filter(user_id=user_id).order_by('-id').first()
        elif expense_id:
            expense = Expense.objects.filter(user_id=user_id, id=expense_id).first()
        else:
            return "Please specify which expense to delete (last one or a specific ID)."
        
        if not expense:
            return "No matching expense found."

        details = f"{expense.title} (${expense.amount})"
        expense.delete()
        return f"Successfully deleted: {details}"
        
    except Exception as e:
        return f"Error deleting expense: {str(e)}"

@tool
def update_expense(user_id: int, expense_id: int, amount: Optional[float] = None, category: Optional[str] = None, date: Optional[str] = None, description: Optional[str] = None):
    """
    Update an existing expense in the database.
    
    Args:
        user_id: The ID of the user
        expense_id: The ID of the expense to update
        amount: New amount (optional)
        category: New category (optional)
        date: New date (optional)
        description: New description (optional)
    
    Returns:
        Success message with updated expense details
    """
    try:
        # Find the expense
        expense = Expense.objects.filter(user_id=user_id, id=expense_id).first()
        if not expense:
            return f"Expense with ID {expense_id} not found"
        
        # Update fields if provided
        updated_fields = []
        
        if amount is not None:
            expense.amount = Decimal(str(amount))
            updated_fields.append(f"amount to ${amount}")
        
        if category:
            expense.category = category.lower()
            updated_fields.append(f"category to {category}")
        
        if date:
            if date == 'today':
                expense.date = timezone.now().date()
            else:
                try:
                    expense.date = timezone.datetime.strptime(date, '%Y-%m-%d').date()
                except:
                    expense.date = timezone.now().date()
            updated_fields.append(f"date to {expense.date.strftime('%Y-%m-%d')}")
        
        if description:
            expense.title = description
            updated_fields.append("description")
        
        if not updated_fields:
            return "No fields to update"
        
        # Save changes
        expense.save()
        
        return f"Successfully updated expense: {', '.join(updated_fields)}"
        
    except Exception as e:
        return f"Error updating expense: {str(e)}"

# --- 3. Graph Logic ---
def get_expense_agent(api_key: str):
    """
    Create and return the LangGraph expense agent.
    
    Args:
        api_key: Groq API key for LLM access
    
    Returns:
        Compiled LangGraph agent
    """
    # Initialize Groq Llama 3.1 8B (using current supported model)
    llm = ChatGroq(
        groq_api_key=api_key,
        model_name="llama-3.1-8b-instant",
        temperature=0
    )

    tools = [
        query_expenses,
        get_spending_stats,
        add_expense,
        delete_expense,
        update_expense
    ]
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    def call_model(state: AgentState):
        """Agent node that decides what to do next"""
        messages = state['messages']
        
        # Inject system prompt if it's the first message
        if not any(isinstance(m, SystemMessage) for m in messages):
            sys_msg = SystemMessage(content=(
                f"You are a helpful Finance Assistant for UID {state['user_id']}. ALWAYS respond with a SHORT friendly message!\n\n"
                "CRITICAL - UNDERSTAND USER INTENT FIRST:\n"
                "🗑️ DELETE/REMOVE/CLEAR/UNDO → use delete_expense ONLY (never get_spending_stats!)\n"
                "➕ ADD/RECORD/SPENT/EXPENSE → use add_expense\n"
                "📊 STATS/TOTAL/REPORT/SUMMARY → use get_spending_stats\n"
                "🔍 SEARCH/LIST/QUERY/SHOW → use query_expenses\n"
                "✏️ UPDATE/MODIFY/CHANGE → use update_expense\n\n"
                "TOOL PARAMETER RULES:\n"
                "add_expense: MUST have user_id, amount (float), category\n"
                "  - Optional: date_str in DD-MM-YYYY format (e.g., '05-05-2002')\n"
                "  - If no date: uses today\n"
                "delete_expense: MUST have user_id, AND (expense_id OR delete_last=true)\n"
                "  - For 'delete last': use delete_last=true\n"
                "  - For 'delete all': say 'Cannot delete all - only one at a time'\n"
                "query_expenses: user_id, optional: query_str, category, period\n"
                "get_spending_stats: user_id, optional: period, category\n"
                "update_expense: user_id, expense_id, optional: amount/category/date/description\n\n"
                "KEYWORD MAPPING:\n"
                "DELETE keywords: delete, remove, clear, undo, erase, destroy, discard\n"
                "ADD keywords: add, record, spent, expense, paid, charge, payment\n"
                "STATS keywords: stats, total, how much, report, summary, spending\n"
                "SEARCH keywords: search, list, show, find, query, which, recent\n"
                "CATEGORY: mobile/recharge → bills, car/petrol/fuel → travel, movie/game → entertainment\n\n"
                "CRITICAL: If user says DELETE, ALWAYS call delete_expense, never call get_spending_stats!\n"
            ))
            messages = [sys_msg] + messages
        
        try:
            # Check if last message is a ToolMessage - if so, just respond with acknowledgment
            last_msg = messages[-1]
            if isinstance(last_msg, ToolMessage):
                # Tool was just executed, generate a friendly response
                logger.info(f"Last message is ToolMessage, generating response...")
                try:
                    response = llm_with_tools.invoke(messages, max_tokens=100)
                    # Ensure we got a response with content
                    if response and hasattr(response, 'content') and response.content:
                        logger.info(f"✅ Generated response after tool: {response.content[:60]}")
                        return {"messages": [response]}
                except Exception as e:
                    logger.error(f"❌ Error generating response: {str(e)}")
                    return {"messages": [AIMessage(content="Sorry, I had trouble processing that. Please try again.")]}

            # Use limited max_tokens for faster reasoning
            response = llm_with_tools.invoke(messages, max_tokens=150)
            
            # --- CRITICAL ARGUMENT CLEANER & VALIDATOR ---
            if response.tool_calls:
                # Get the user's message for intent detection
                user_msg = ""
                for m in reversed(messages):
                    if isinstance(m, HumanMessage):
                        user_msg = m.content.lower()
                        break
                
                # Intent detection keywords
                add_keywords = ['add', 'spent', 'kharch', 'expense', 'payment', 'charge', 'rs', '₹', 'rupees', 'recorded', 'paid']
                delete_keywords = ['delete', 'remove', 'undo', 'cancel', 'revert', 'clear', 'erase', 'destroy', 'discard']
                delete_all_keywords = ['all', 'poora', 'sab', 'entire', 'everything', 'whole']
                stats_keywords = ['stats', 'total', 'how much', 'report', 'summary', 'spending']
                
                user_wants_add = any(keyword in user_msg for keyword in add_keywords)
                user_wants_delete = any(keyword in user_msg for keyword in delete_keywords)
                user_wants_delete_all = any(keyword in user_msg for keyword in delete_all_keywords)
                user_wants_stats = any(keyword in user_msg for keyword in stats_keywords)
                
                # Handle "delete all" - not supported, send friendly message
                if user_wants_delete and user_wants_delete_all:
                    logger.info(f"User wants to delete ALL expenses - not supported. Returning helpful message.")
                    return {"messages": [AIMessage(content="❌ Can't delete all at once for safety! But I can:\n• Delete the last expense: say 'delete last'\n• Delete a specific expense (if you know ID): say 'delete ID 5'\nBetter safe than sorry! 😊")]}
                
                # Force DELETE tool if user clearly said "delete" (but not "delete all")
                if user_wants_delete and not user_wants_add and not user_wants_delete_all:
                    for tool_call in response.tool_calls:
                        if tool_call.get('name') != 'delete_expense':
                            logger.warning(f"User said DELETE but LLM called {tool_call.get('name')}. Forcing delete_expense.")
                            tool_call['name'] = 'delete_expense'
                            tool_call['args'] = {
                                'user_id': state['user_id'],
                                'delete_last': True  # Default to deleting last expense
                            }
                
                # 1. Force only first tool call for speed
                if len(response.tool_calls) > 1:
                    response.tool_calls = [response.tool_calls[0]]
                
                # 2. Strict argument validation per tool
                for tool_call in response.tool_calls:
                    args = tool_call.get('args', {})
                    t_name = tool_call.get('name')
                    
                    # Safety: If user clearly wants to ADD but delete was called, override it
                    if user_wants_add and not user_wants_delete and t_name == 'delete_expense':
                        # User said ADD but model called DELETE - switch to add_expense
                        # Extract amount and category from context if possible
                        amount_match = re.search(r'(\d+(?:\.\d+)?)', user_msg)
                        if amount_match:
                            amount = float(amount_match.group(1))
                            # Guess category from message
                            category = 'others'
                            for keyword in ['petrol', 'gas', 'fuel']:
                                if keyword in user_msg:
                                    category = 'travel'
                                    break
                            # Create new tool call for add_expense
                            tool_call['name'] = 'add_expense'
                            tool_call['args'] = {
                                'user_id': state['user_id'],
                                'amount': amount,
                                'category': category,
                                'description': f"{category} expense"
                            }

                    # Delete tool - ensure valid args only
                    if t_name == 'delete_expense':
                        valid_keys = {'user_id', 'expense_id', 'delete_last'}
                        # Keep only valid keys with non-None values
                        new_args = {k: v for k, v in args.items() if k in valid_keys and v is not None}
                        tool_call['args'] = new_args
                        # Ensure at least one deletion method
                        if not new_args.get('expense_id') and not new_args.get('delete_last'):
                            tool_call['args']['delete_last'] = False
                    
                    # For add_expense, don't modify - let it go as-is from LLM
                    # The system prompt ensures valid args
                    
                    # For other tools, just remove None values
                    elif t_name not in ['add_expense']:
                        tool_call['args'] = {k: v for k, v in args.items() if v is not None}
            # --- END ARGUMENT CLEANER ---
            
            return {"messages": [response]}
            
        except Exception as e:
            # Handle tool calling errors gracefully
            error_response = f"I encountered an error while processing your request: {str(e)}. Please try rephrasing your request."
            return {"messages": [AIMessage(content=error_response)]}

    # Build the State Machine
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("action", ToolNode(tools))

    # Define edges
    workflow.set_entry_point("agent")
    
    def router(state: AgentState):
        """Route to action node if tools are called, otherwise end"""
        last_msg = state['messages'][-1]
        if last_msg.tool_calls:
            return "continue"
        return "end"

    workflow.add_conditional_edges("agent", router, {"continue": "action", "end": END})
    workflow.add_edge("action", "agent")

    return workflow.compile()
