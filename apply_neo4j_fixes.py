#!/usr/bin/env python3
"""
Apply the exact Neo4j Cypher syntax fixes from NEO4J_CYPHER_SYNTAX_BUG_TRACKING.md
"""

def apply_fixes():
    # Read the file
    with open('mem0/memory/graph_memory.py', 'r') as f:
        content = f.read()
    
    # Fix 1: get_all() method - Replace WHERE 1=1 {agent_filter} with proper node properties
    content = content.replace(
        'WHERE 1=1 {agent_filter}',
        ''
    )
    
    # Fix 2: Replace agent_filter usage in search method
    content = content.replace(
        '{agent_filter}',
        ''
    ).replace(
        '{agent_filter.replace("n.", "m.")}',
        ''
    )
    
    # Now apply the proper node property syntax
    # Fix get_all method
    old_get_all = '''        agent_filter = ""
        params = {"user_id": filters["user_id"], "limit": limit}
        if filters.get("agent_id"):
            agent_filter = ""
            params["agent_id"] = filters["agent_id"]

        query = f"""
        MATCH (n {self.node_label} {{user_id: $user_id}})-[r]->(m {self.node_label} {{user_id: $user_id}})
        
        RETURN n.name AS source, type(r) AS relationship, m.name AS target
        LIMIT $limit
        """"'''
    
    new_get_all = '''        params = {"user_id": filters["user_id"], "limit": limit}
        
        # Build node properties based on filters
        node_props = ["user_id: $user_id"]
        if filters.get("agent_id"):
            node_props.append("agent_id: $agent_id")
            params["agent_id"] = filters["agent_id"]
        node_props_str = ", ".join(node_props)

        query = f"""
        MATCH (n {self.node_label} {{{node_props_str}}})-[r]->(m {self.node_label} {{{node_props_str}}})
        RETURN n.name AS source, type(r) AS relationship, m.name AS target
        LIMIT $limit
        """"'''
    
    content = content.replace(old_get_all, new_get_all)
    
    # Write the fixed content back
    with open('mem0/memory/graph_memory.py', 'w') as f:
        f.write(content)
    
    print("Successfully applied Neo4j Cypher syntax fixes!")

if __name__ == "__main__":
    apply_fixes()
