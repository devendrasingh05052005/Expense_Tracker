"""
Streaming AI Agent Views for Real-time Response"""

import json
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
from langchain_core.messages import HumanMessage
from .agents import get_expense_agent


@login_required
@csrf_exempt
def ai_agent_stream(request):
    """Streaming AI endpoint for real-time response"""
    if request.method != 'POST':
        return StreamingHttpResponse('Method not allowed', status=405)

    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return StreamingHttpResponse('No message provided', status=400)

        # Initialize agent
        app = get_expense_agent(settings.GROQ_API_KEY)
        
        inputs = {
            "messages": [HumanMessage(content=user_message)],
            "user_id": request.user.id
        }
        
        config = {"configurable": {"thread_id": str(request.user.id)}}

        def event_stream():
            """Stream AI responses in Server-Sent Events format"""
            try:
                for chunk, metadata in app.stream(inputs, config=config, stream_mode="messages"):
                    # Check if chunk has content
                    if hasattr(chunk, 'content') and chunk.content:
                        # Format as SSE: "data: {json}\n\n"
                        chunk_data = {
                            'content': chunk.content,
                            'type': 'message'
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                    # Handle tool execution results
                    elif hasattr(chunk, 'tool_calls'):
                        chunk_data = {
                            'tool_calls': chunk.tool_calls,
                            'type': 'tool_call'
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                        
            except Exception as e:
                error_data = {
                    'error': str(e),
                    'type': 'error'
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            }
        )

    except Exception as e:
        error_data = {
            'error': f'Streaming error: {str(e)}',
            'type': 'stream_error'
        }
        
        def error_stream():
            yield f"data: {json.dumps(error_data)}\n\n"
            
        return StreamingHttpResponse(
            error_stream(),
            content_type='text/event-stream',
            status=500
        )
