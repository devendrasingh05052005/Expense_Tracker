"""
Streaming AI Agent Views for Real-time Response"""

import json
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from .agents import get_cached_agent
import logging

logger = logging.getLogger(__name__)


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

        # Get cached agent (much faster)
        agent = get_cached_agent(settings.GROQ_API_KEY)
        
        inputs = {
            "messages": [HumanMessage(content=user_message)],
            "user_id": request.user.id
        }

        def stream():
            """Stream AI responses in Server-Sent Events format"""
            try:
                seen_content = set()  # Track what we've already sent
                
                logger.info(f"🟢 Starting stream: user_message='{user_message}'")
                
                # Invoke agent and collect all updates
                for output in agent.stream(inputs):
                    try:
                        if not output:
                            logger.debug("Empty output, skipping")
                            continue
                        
                        logger.debug(f"Processing nodes: {list(output.keys())}")
                        
                        # output = {node_name: {'messages': [...]}}
                        for node_name, node_out in output.items():
                            if not isinstance(node_out, dict) or 'messages' not in node_out:
                                logger.debug(f"Skipping {node_name} - no messages")
                                continue
                            
                            messages = node_out.get('messages', [])
                            logger.debug(f"Node '{node_name}' has {len(messages)} messages")
                            
                            # Process ALL messages, but only send new ones
                            for msg in messages:
                                msg_type = type(msg).__name__
                                
                                # Send AI text messages (if not already sent)
                                if isinstance(msg, AIMessage):
                                    msg_content = msg.content
                                    if msg_content and msg_content not in seen_content:
                                        seen_content.add(msg_content)
                                        logger.info(f"📤 Sending AIMessage: {msg_content[:60]}")
                                        yield f"data: {json.dumps({'type': 'text', 'content': msg_content})}\n\n"
                                    else:
                                        logger.debug(f"Skipping AIMessage (duplicate or empty)")
                                
                                # Send tool execution results
                                elif isinstance(msg, ToolMessage):
                                    content = str(msg.content) if msg.content else "(empty)"
                                    if content and content not in seen_content:
                                        seen_content.add(content)
                                        logger.info(f"📤 Sending ToolMessage: {content[:60]}")
                                        yield f"data: {json.dumps({'type': 'tool_result', 'content': content})}\n\n"
                                    else:
                                        logger.debug(f"Skipping ToolMessage (duplicate or empty)")
                    
                    except Exception as e:
                        logger.exception(f"❌ Error in stream loop: {e}")
                        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
                
                logger.info(f"🔴 Stream complete - sent {len(seen_content)} unique messages")
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
                        
            except Exception as e:
                logger.exception(f"❌ Stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingHttpResponse(
            stream(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        logger.exception(f"Request handling error: {e}")
        error_data = {
            'type': 'error',
            'error': str(e)
        }
        
        def error_stream():
            yield f"data: {json.dumps(error_data)}\n\n"
            
        return StreamingHttpResponse(
            error_stream(),
            content_type='text/event-stream',
            status=500
        )
