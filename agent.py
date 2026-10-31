import json
import time
from groq import Groq
from support_agent.models import AgentResult, Principal
from support_agent.service import AuthorizationError, StudentService

TOOLS=[{"type":"function","function":{"name":"get_my_fee_status","description":"Read only the authenticated student's own fee and scholarship status.","parameters":{"type":"object","properties":{},"additionalProperties":False}}},{"type":"function","function":{"name":"request_email_change","description":"Create a pending approval request for the authenticated student's email.","parameters":{"type":"object","properties":{"new_email":{"type":"string"}},"required":["new_email"],"additionalProperties":False}}},{"type":"function","function":{"name":"get_my_requests","description":"Read only the authenticated student's own approval requests.","parameters":{"type":"object","properties":{},"additionalProperties":False}}}]

def run_agent(settings, principal: Principal, message: str) -> AgentResult:
    started=time.perf_counter(); service=StudentService(settings.database_path, principal)
    messages=[{"role":"system","content":"Use tools for private facts. Tools enforce identity. Never claim access to another student. Email changes are pending until reviewer approval."},{"role":"user","content":message}]
    client=Groq(api_key=settings.groq_api_key); used=[]; prompt=completion=0
    for _ in range(5):
        response=client.chat.completions.create(model=settings.groq_model,messages=messages,tools=TOOLS,tool_choice="auto",temperature=0)
        usage=response.usage; prompt+=getattr(usage,"prompt_tokens",0) or 0; completion+=getattr(usage,"completion_tokens",0) or 0
        reply=response.choices[0].message; calls=reply.tool_calls or []
        if not calls: return AgentResult((reply.content or "No response.").strip(),round((time.perf_counter()-started)*1000),prompt,completion,tuple(used))
        messages.append(reply)
        for call in calls:
            used.append(call.function.name)
            try:
                args=json.loads(call.function.arguments)
                if call.function.name=="get_my_fee_status": payload=service.my_fee_status()
                elif call.function.name=="request_email_change": payload=service.request_email_change(args["new_email"])
                elif call.function.name=="get_my_requests": payload=service.my_requests()
                else: payload={"error":"Unknown tool."}
            except (AuthorizationError,ValueError,KeyError) as error: payload={"error":str(error)}
            messages.append({"role":"tool","tool_call_id":call.id,"name":call.function.name,"content":json.dumps(payload)})
    return AgentResult("Tool limit reached.",round((time.perf_counter()-started)*1000),prompt,completion,tuple(used))

