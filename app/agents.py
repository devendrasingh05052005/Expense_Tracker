import os
from typing import Annotated, TypedDict, List, Optional
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from django.db.models import Sum, Q, Count, Avg
from django.utils import timezone
from decimal import Decimal
from .models import Expense

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
def add_expense(user_id: int, amount: float, category: str, date: str = None, description: str = None):
    """
    Add a new expense to the database.
    
    Args:
        user_id: The ID of the user
        amount: The amount spent
        category: Category of expense (food, travel, shopping, bills, health, entertainment, others)
        date: Date of expense (YYYY-MM-DD format or 'today')
        description: Optional description/title for the expense
    
    Returns:
        Success message with expense details
    """
    try:
        # Parse date
        if date == 'today' or not date:
            expense_date = timezone.now().date()
        else:
            try:
                expense_date = timezone.datetime.strptime(date, '%Y-%m-%d').date()
            except:
                expense_date = timezone.now().date()
        
        # Create expense
        expense = Expense.objects.create(
            user_id=user_id,
            amount=Decimal(str(amount)),
            category=category.lower(),
            title=description or f'{category} expense',
            date=expense_date
        )
        
        return f"Successfully added expense: ${amount} for {category} on {expense_date.strftime('%Y-%m-%d')}"
        
    except Exception as e:
        return f"Error adding expense: {str(e)}"

@tool
def delete_expense(user_id: int, expense_id: Optional[int] = None, delete_last: Optional[bool] = False):
    """
    Delete an expense. ONLY use if user explicitly says DELETE/REMOVE/HATAYA.
    
    Args:
        user_id: The ID of the user (REQUIRED)
        expense_id: Specific expense ID to delete (Optional)
        delete_last: Set to True to delete the most recent expense (Optional)
    
    Returns:
        Success message with deleted expense details
    """
    try:
        if delete_last:
            # Delete the most recent expense
            expense = Expense.objects.filter(user_id=user_id).order_by('-date').first()
        elif expense_id:
            # Delete specific expense
            expense = Expense.objects.filter(user_id=user_id, id=expense_id).first()
        else:
            return "Error: Either provide expense_id or set delete_last=True"
        
        if not expense:
            return "No expense found to delete"
        
        # Store details before deletion
        details = f"${expense.amount} for {expense.category} on {expense.date.strftime('%Y-%m-%d')}"
        
        # Delete the expense
        expense.delete()
        
        return f"Successfully deleted expense: {details}"
        
    except Exception as e:
        return f"Error deleting expense: {str(e)}"

@tool
def update_expense(user_id: int, expense_id: int, amount: float = None, category: str = None, date: str = None, description: str = None):
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
    # Initialize Groq Llama 3 (using current supported model)
    llm = ChatGroq(
        groq_api_key=api_key,
        model_name="llama-3.1-8b-instant",
        temperature=0  # Critical for deterministic tool calling
    )

    # Define available tools
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
                f"You are a DATA REPORTER for user ID: {state['user_id']}. "
                "Your job is to call tools and report their output EXACTLY as returned.\n"
                "RULES:\n"
                "1. DO NOT apologize. DO NOT explain how tools work.\n"
                "2. DO NOT add extra information. Report only what tools return.\n"
                "3. DO NOT say 'however', 'I must note', 'the actual output would be'.\n"
                "4. For 'kitna kharcha', 'total expense' → ONLY use get_spending_stats\n"
                "5. For 'find', 'show' → ONLY use query_expenses\n"
                "6. For 'add', 'kharch kiya' → ONLY use add_expense\n"
                "7. For 'delete', 'remove', 'hataya' → ONLY use delete_expense\n"
                "8. For 'update', 'change', 'modify' → ONLY use update_expense\n"
                "9. Call only ONE tool per response.\n"
                "10. If user asks about travel expenses, use query_expenses with category='travel'\n"
                "11. Valid categories: food, travel, shopping, bills, health, entertainment, others\n"
                "12. Valid dates: today, yesterday, this_month, last_month, YYYY-MM-DD\n"
                "13. If confused, ask for clarification.\n"
                "\n"
                "AVAILABLE TOOLS:\n"
                "- query_expenses: Search/list expenses\n"
                "- get_spending_stats: Calculate totals and statistics\n"
                "- add_expense: Add new expense\n"
                "- update_expense: Modify existing expense\n"
            ))
            messages = [sys_msg] + messages
        
        try:
            response = llm_with_tools.invoke(messages)
            
            # Validate tool calls
            if response.tool_calls:
                valid_tools = ['query_expenses', 'get_spending_stats', 'add_expense', 'delete_expense', 'update_expense']
                
                # Filter out invalid tool calls
                valid_tool_calls = []
                for tool_call in response.tool_calls:
                    if tool_call.get('name') in valid_tools:
                        valid_tool_calls.append(tool_call)
                
                if not valid_tool_calls:
                    # All tool calls were invalid
                    from langchain_core.messages import AIMessage
                    error_response = "I tried to use an unavailable tool. Let me help you differently. What would you like to know about your expenses?"
                    return {"messages": [AIMessage(content=error_response)]}
                
                # Keep only valid tool calls
                response.tool_calls = valid_tool_calls
                
                # Check if multiple tools are being called
                if len(response.tool_calls) > 1:
                    # Create a new response with only the first tool call
                    first_tool = response.tool_calls[0]
                    response.tool_calls = [first_tool]
            
            return {"messages": [response]}
            
        except Exception as e:
            # Handle tool calling errors gracefully
            from langchain_core.messages import AIMessage
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
    workflow.add_edge("agent", END)

    return workflow.compile()
