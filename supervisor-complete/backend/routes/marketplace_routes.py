"""SkillHub marketplace endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from marketplace import skillhub, MarketplaceListing

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


@router.get("/search")
async def marketplace_search(query: str = "", category: str = "",
                              item_type: str = "", sort_by: str = "installs",
                              limit: int = 20, offset: int = 0):
    """Search the SkillHub marketplace."""
    return skillhub.search(query=query, category=category, item_type=item_type,
                           sort_by=sort_by, limit=limit, offset=offset)


@router.get("/featured")
async def marketplace_featured():
    """Get featured marketplace items."""
    return {"featured": [f.model_dump() for f in skillhub.get_featured()]}


@router.get("/categories")
async def marketplace_categories():
    """Get marketplace category summary."""
    return {"categories": skillhub.get_categories_summary()}


@router.post("/publish")
async def marketplace_publish(request: Request):
    """Publish an item to the marketplace."""
    body = await request.json()
    listing = MarketplaceListing(**body)
    result = skillhub.publish(listing)
    return result.model_dump()


@router.post("/{listing_id}/install")
async def marketplace_install(listing_id: str, request: Request):
    """Install a marketplace item."""
    body = await request.json()
    item = skillhub.install(listing_id, body.get("user_id", ""), body.get("campaign_id", ""))
    if not item:
        raise HTTPException(404, "Listing not found")
    return {"installed": True, "listing_id": listing_id}


@router.post("/{listing_id}/review")
async def marketplace_review(listing_id: str, request: Request):
    """Add a review to a marketplace listing."""
    body = await request.json()
    review = skillhub.add_review(listing_id, body.get("user_id", ""),
                                  body.get("rating", 5), body.get("comment", ""))
    if not review:
        raise HTTPException(404, "Listing not found")
    return review.model_dump()


@router.get("/{listing_id}")
async def marketplace_get_listing(listing_id: str):
    """Get a marketplace listing."""
    listing = skillhub.get_listing(listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    reviews = skillhub.get_reviews(listing_id)
    return {**listing.model_dump(), "reviews": [r.model_dump() for r in reviews]}


@router.get("/creator/{user_id}/earnings")
async def marketplace_creator_earnings(user_id: str):
    """Get creator earnings from marketplace."""
    return skillhub.get_creator_earnings(user_id)
