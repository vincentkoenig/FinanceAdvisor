from mcp.server.mcpserver import MCPServer

mcp = MCPServer("FinanceAdvisor")

@mcp.tool()
def hello_portfolio() -> str:
    """Gibt eine Testnachricht zurück, um die Verbindung zu prüfen."""
    return "Verbindung zum FinanceAdvisor MCP-Server steht!"

if __name__ == "__main__":
    mcp.run()