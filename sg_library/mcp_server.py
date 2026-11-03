"""Local stdio MCP server. No media, metadata, or models leave this computer."""
from mcp.server.fastmcp import FastMCP
from .client import Client

mcp = FastMCP('Smart Media Manager')
client = Client()


@mcp.tool()
def library_status() -> dict:
    """Check gallery availability, archive location, and authorized source folders."""
    return client.call('health')


@mcp.tool()
def search_outputs(query: str = '', limit: int = 50) -> dict:
    """Find generated outputs by filename. Returns IDs and local paths, not media content."""
    return client.call('outputs', q=query, limit=limit)


@mcp.tool()
def search_library(query: str = '', limit: int = 100) -> dict:
    """Search saved asset titles, tags, notes, collections, filenames, and sourced facts."""
    return client.call('assets', q=query, limit=limit)


@mcp.tool()
def save_keeper(source_path: str, title: str = '', collection: str = '', actor: str = 'agent') -> dict:
    """Copy an authorized local output/input and full available workflows into permanent storage.
    Existing byte-identical assets are returned without duplication. Never deletes sources.
    """
    return client.call('assets', 'POST', dict(source_path=source_path, title=title, collection=collection, actor=actor))


@mcp.tool()
def get_asset(asset_id: str) -> dict:
    """Read immutable generation evidence, editable metadata, and revision history."""
    return client.call('assets/' + asset_id)


@mcp.tool()
def update_metadata(asset_id: str, expected_revision: int, fields: dict, actor: str, reason: str) -> dict:
    """Update title, notes, tags, collection, rating (1-5/null), or facts after reading the record.
    Facts require key/value/source_type (user/author/verified/inferred); optional source_url,
    checked_at and notes. Preserve unrelated fields and existing facts. Cite research sources.
    Conflicts require rereading and merging; never blindly retry an old full-field replacement.
    """
    return client.call('assets/' + asset_id, 'PATCH', dict(expected_revision=expected_revision, fields=fields, actor=actor, reason=reason))


@mcp.tool()
def get_workflow(asset_id: str, kind: str = 'ui') -> dict:
    """Read the full archived workflow: ui graph or api execution prompt. Does not run it."""
    return client.call('assets/' + asset_id + '/workflow', kind=kind)


@mcp.tool()
def verify_archive(asset_id: str) -> dict:
    """Verify media, workflows and captured reference hashes; list unresolved references."""
    return client.call('assets/' + asset_id + '/verify')


@mcp.tool()
def restore_metadata(asset_id: str, revision: int, expected_revision: int, actor: str) -> dict:
    """Restore a historical editorial snapshot as a new revision, preserving all history."""
    return client.call('assets/' + asset_id + '/restore', 'POST', dict(revision=revision, expected_revision=expected_revision, actor=actor))


if __name__ == '__main__':
    mcp.run(transport='stdio')
