"""FastAPI application for API-key access to Geode data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geode.api.auth import ApiAuthError, ApiPrincipal, authenticate_api_key, default_key_file
from geode.api.exports import create_export, export_path
from geode.api.logging import log_usage
from geode.api.rate_limit import ApiRateLimitError, check_rate_limit
from geode.api.store import GeodeDataStore, GeodeRecordNotFoundError


def create_app(project_root: Path | None = None, key_file: Path | None = None) -> Any:
    """Create the optional FastAPI application."""

    try:
        from fastapi import Depends, FastAPI, Header, HTTPException, Query
        from fastapi.responses import FileResponse
    except ImportError as exc:
        raise RuntimeError("FastAPI is not installed. Install the geode api extra.") from exc

    root = (project_root or Path.cwd()).resolve()
    keys = (key_file or default_key_file(root)).resolve()
    store = GeodeDataStore(root)
    app = FastAPI(title="Geode Data API", version="0.1.0")

    def require_scope(scope: str) -> Any:
        """Build a FastAPI dependency that checks one permission."""

        def dependency(x_geode_api_key: str | None = Header(default=None)) -> ApiPrincipal:
            try:
                principal = authenticate_api_key(x_geode_api_key, keys, scope)
                check_rate_limit(root, principal)
                return principal
            except ApiAuthError as exc:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
            except ApiRateLimitError as exc:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        return dependency

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return a simple process health response."""

        return {"status": "ok", "project_root": root.as_posix()}

    @app.get("/v1/manifest")
    def manifest(
        principal: ApiPrincipal = Depends(require_scope("manifest:read")),
    ) -> dict[str, Any]:
        """Return the Geode master manifest."""

        response = store.manifest()
        log_usage(root, principal, "GET", "/v1/manifest", 200)
        return response

    @app.get("/v1/statutes/{statute_id}")
    def statute(
        statute_id: str,
        principal: ApiPrincipal = Depends(require_scope("statutes:read")),
    ) -> dict[str, Any]:
        """Return one CRS statute record."""

        try:
            response = store.get_statute(statute_id)
        except GeodeRecordNotFoundError as exc:
            log_usage(root, principal, "GET", "/v1/statutes/{statute_id}", 404, statute_id)
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_usage(root, principal, "GET", "/v1/statutes/{statute_id}", 200, statute_id)
        return response

    @app.get("/v1/regulations/{regulation_id}")
    def regulation(
        regulation_id: str,
        principal: ApiPrincipal = Depends(require_scope("regulations:read")),
    ) -> dict[str, Any]:
        """Return one CCR regulation record."""

        try:
            response = store.get_regulation(regulation_id)
        except GeodeRecordNotFoundError as exc:
            log_usage(root, principal, "GET", "/v1/regulations/{regulation_id}", 404, regulation_id)
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_usage(root, principal, "GET", "/v1/regulations/{regulation_id}", 200, regulation_id)
        return response

    @app.get("/v1/search")
    def search(
        q: str,
        layers: list[str] | None = Query(default=None),
        limit: int = 20,
        principal: ApiPrincipal = Depends(require_scope("search:read")),
    ) -> dict[str, Any]:
        """Search Geode layer indexes."""

        try:
            response = store.search(q, layers=layers, limit=limit)
        except ValueError as exc:
            log_usage(root, principal, "GET", "/v1/search", 400, str(exc))
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        log_usage(root, principal, "GET", "/v1/search", 200, q)
        return response

    @app.post("/v1/exports")
    def exports(
        payload: dict[str, Any],
        principal: ApiPrincipal = Depends(require_scope("exports:create")),
    ) -> dict[str, object]:
        """Create a bulk export package."""

        try:
            result = create_export(
                root,
                principal,
                layers=payload.get("layers"),
                include_crosswalks=bool(payload.get("include_crosswalks", True)),
            )
        except (PermissionError, ValueError) as exc:
            log_usage(root, principal, "POST", "/v1/exports", 400, str(exc))
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        log_usage(root, principal, "POST", "/v1/exports", 201, result.export_id)
        return result.to_dict(root)

    @app.get("/v1/exports/{export_id}/download")
    def download_export(
        export_id: str,
        principal: ApiPrincipal = Depends(require_scope("exports:download")),
    ) -> Any:
        """Download a previously created export package."""

        try:
            path = export_path(root, export_id)
        except (ValueError, FileNotFoundError) as exc:
            log_usage(root, principal, "GET", "/v1/exports/{export_id}/download", 404, export_id)
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_usage(root, principal, "GET", "/v1/exports/{export_id}/download", 200, export_id)
        return FileResponse(path, media_type="application/zip", filename=path.name)

    return app


def main() -> None:
    """Run the API with Uvicorn."""

    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("Uvicorn is not installed. Install the geode web extra.") from exc
    uvicorn.run("geode.api.app:create_app", factory=True, host="127.0.0.1", port=8000)
