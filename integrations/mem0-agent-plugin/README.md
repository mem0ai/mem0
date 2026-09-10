# Mem0 portable agent plugin

This Agent Plugins v1 package provides the local `search_memories` MCP tool and six memory skills for compatible hosts.

Sidekick is exclusive to the [Claude Code plugin](../claude-code-plugin/README.md#sonnet-sidekick-agent). This portable package contains no agent declarations, lifecycle hooks, or worktree management.

The portable package has no automatic capture or memory write tool. Its bundled `remember` skill cannot save new memories on its own. Use a native Mem0 plugin when you need automatic capture.

The generated memory runtime and skills come from [agent-plugin-core](../agent-plugin-core/README.md).
