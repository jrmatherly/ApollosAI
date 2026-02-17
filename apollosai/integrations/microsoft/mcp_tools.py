"""MCP tool definitions for Microsoft 365 integration.

Exposes Graph API operations as MCP tools that can be used
by the OpenHands agent during conversations.
"""

import logging

logger = logging.getLogger(__name__)

# MCP tool definitions to be registered with the MCP server
MICROSOFT_MCP_TOOLS = [
    {
        'name': 'microsoft_search_documents',
        'description': 'Search for documents in Microsoft 365 (SharePoint, OneDrive)',
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'Search query string',
                },
                'site_id': {
                    'type': 'string',
                    'description': 'Optional SharePoint site ID to scope search',
                },
            },
            'required': ['query'],
        },
    },
    {
        'name': 'microsoft_read_file',
        'description': 'Read a file from OneDrive or SharePoint by drive and item ID',
        'parameters': {
            'type': 'object',
            'properties': {
                'drive_id': {
                    'type': 'string',
                    'description': 'The drive ID containing the file',
                },
                'item_id': {
                    'type': 'string',
                    'description': 'The item ID of the file',
                },
            },
            'required': ['drive_id', 'item_id'],
        },
    },
    {
        'name': 'microsoft_list_emails',
        'description': 'List recent emails for the current user',
        'parameters': {
            'type': 'object',
            'properties': {
                'count': {
                    'type': 'integer',
                    'description': 'Number of emails to retrieve (default 10)',
                    'default': 10,
                },
            },
        },
    },
]


async def handle_mcp_tool_call(
    tool_name: str, arguments: dict, access_token: str
) -> dict:
    """Dispatch an MCP tool call to the appropriate Graph API operation."""
    from apollosai.integrations.microsoft.service import GraphService

    service = GraphService(access_token)

    if tool_name == 'microsoft_search_documents':
        return await service.search_documents(
            query=arguments['query'],
            site_id=arguments.get('site_id'),
        )

    if tool_name == 'microsoft_read_file':
        return await service.get_drive_item(
            drive_id=arguments['drive_id'],
            item_id=arguments['item_id'],
        )

    if tool_name == 'microsoft_list_emails':
        # user_id='me' requires delegated permissions; use stored user_id if available
        return await service.list_messages(
            user_id='me',
            top=arguments.get('count', 10),
        )

    return {'error': f'Unknown tool: {tool_name}'}
