from mem0.llms.utils.tools import (
    ADD_MEMORY_TOOL,
    DELETE_MEMORY_TOOL,
    UPDATE_MEMORY_TOOL,
)
from mem0.llms.utils.tools_cn import (
    ADD_MEMORY_TOOL_CN,
    DELETE_MEMORY_TOOL_CN,
    UPDATE_MEMORY_TOOL_CN,
)

from mem0.configs.prompts import (MEMORY_DEDUCTION_PROMPT,SYSTEM_PROMPT)
from mem0.configs.prompts_cn import (MEMORY_DEDUCTION_PROMPT_CN,SYSTEM_PROMPT_CN)

class LocalData:
    def __init__(self,local:str):
        self.SYSTEM_PROMPT=SYSTEM_PROMPT
        self.MEMORY_DEDUCTION_PROMPT=MEMORY_DEDUCTION_PROMPT
        self.ADD_MEMORY_TOOL=ADD_MEMORY_TOOL
        self.DELETE_MEMORY_TOOL=DELETE_MEMORY_TOOL
        self.UPDATE_MEMORY_TOOL=UPDATE_MEMORY_TOOL
        if local == "cn":
            self.SYSTEM_PROMPT=SYSTEM_PROMPT_CN
            self.MEMORY_DEDUCTION_PROMPT=MEMORY_DEDUCTION_PROMPT_CN
            self.ADD_MEMORY_TOOL=ADD_MEMORY_TOOL_CN
            self.DELETE_MEMORY_TOOL=DELETE_MEMORY_TOOL_CN
            self.UPDATE_MEMORY_TOOL=UPDATE_MEMORY_TOOL_CN
        

    