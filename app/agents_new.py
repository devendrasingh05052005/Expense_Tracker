import os
from typing import Annotated, TypedDict, List, Optional, Union
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

# --- Singleton Agent (Fastest Response) ---
_AGENT_CACHE = None

# 1. State Definition (Added user_id and context for better tracking)
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: int

# --- 2. Optimized Tools ---

@tool
def manage_expense(
    user_id: int, 
    action: str, 
    amount: Optional[float] = None, 
    category: Optional[str] = "others", 
    description: Optional[str] = "",
    period: Optional[str] = "this_month"
):
    """
    Unified tool to add or calculate expenses. 
    Actions: 'add' or 'stats'.
    """
    try:
        if action == 'add' and amount:
            desc = description if (description and description.strip()) else f"{category} expense"
            Expense.objects.create(
                user_id=user_id,
                amount=Decimal(str(amount)),
                category=category.lower(),
                title=desc,
                date=timezone.now().date()
            )
            return f"Done! Added ${amount} in {category}."
            
        elif action == 'stats':
            expenses = Expense.objects.filter(user_id=user_id)
            # Simple period logic
            if period == 'today':
                expenses = expenses.filter(date=timezone.now().date())
            
            total = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
            return f"Total for {period}: ${total:.2f} (Count: {expenses.count()})"
            
        return "Action not recognized or missing parameters."
    except Exception as e:
        return f"Database error: {str(e)}"

@tool
def list_expenses(user_id: int, count: int = 5):
    """Lists the most recent transactions."""
    expenses = Expense.objects.filter(user_id=user_id).order_by('-date')[:count]
    if not expenses: return "No expenses found."
    return "\n".join([f"- {e.date}: {e.title} (${e.amount})" for e in expenses])

# --- 3. Robust Graph Logic ---

def get_expense_agent(api_key: str):
    llm = ChatGroq(
        groq_api_key=api_key,
        model_name="llama-3.3-70b-versatile", # USE 70B FOR REAL CHATBOT FEEL
        temperature=0.2 # Thodi 'creativity' natural chat ke liye
    )

    tools = [manage_expense, list_expenses]
    llm_with_tools = llm.bind_tools(tools)

    def chatbot(state: AgentState):
        # System Prompt logic
        if not any(isinstance(m, SystemMessage) for m in state['messages']):
            prompt = SystemMessage(content=(
                f"You are a friendly personal finance bro. User ID: {state['user_id']}.\n"
                "1. Keep responses short and Hinglish (Hindi + English mix).\n"
                "2. If adding, just say 'Done!' or 'Ho gaya!'.\n"
                "3. NEVER explain tool logic. Just be a human.\n"
                "4. If user says 'Hi', reply with 'Hey! Kya kharch kiya aaj?'"
            ))
            state['messages'] = [prompt] + state['messages']

        response = llm_with_tools.invoke(state['messages'])
        
        # Clean nulls for Groq safety
        if response.tool_calls:
            for t in response.tool_calls:
                t['args'] = {k: v for k, v in t['args'].items() if v is not None}
                
        return {"messages": [response]}

    # Graph Setup
    builder = StateGraph(AgentState)
    builder.add_node("chatbot", chatbot)
    builder.add_node("tools", ToolNode(tools))
    
    builder.set_entry_point("chatbot")
    
    def router(state: AgentState):
        if state["messages"][-1].tool_calls:
            return "tools"
        return END

    builder.add_conditional_edges("chatbot", router)
    builder.add_edge("tools", "chatbot")
    
    return builder.compile()

def get_cached_agent(api_key: str):
    global _AGENT_CACHE
    if not _AGENT_CACHE:
        _AGENT_CACHE = get_expense_agent(api_key)
    return _AGENT_CACHE
