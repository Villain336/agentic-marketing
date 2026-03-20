"""
Product roadmaps, feature prioritization, user stories, and competitive matrices.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


async def _create_product_roadmap(product_name: str, quarters: str = "4", themes: str = "") -> str:
    """Generate product roadmap specification."""
    theme_list = [t.strip() for t in themes.split(",")] if themes else ["Foundation", "Growth", "Scale", "Optimize"]

    if settings.linear_api_key:
        # Create a Linear project for the roadmap, then add milestones as issues
        graphql_url = "https://api.linear.app/graphql"
        headers = {
            "Authorization": settings.linear_api_key,
            "Content-Type": "application/json",
        }
        # Step 1: fetch the first team ID available
        try:
            team_resp = await _http.post(
                graphql_url,
                json={"query": "{ teams { nodes { id name } } }"},
                headers=headers,
            )
            team_resp.raise_for_status()
            teams = team_resp.json().get("data", {}).get("teams", {}).get("nodes", [])
            team_id = teams[0]["id"] if teams else None

            if team_id:
                # Step 2: create a project for the roadmap
                project_mutation = """
                mutation CreateProject($name: String!, $teamIds: [String!]!) {
                  projectCreate(input: { name: $name, teamIds: $teamIds }) {
                    success
                    project { id name url }
                  }
                }
                """
                proj_resp = await _http.post(
                    graphql_url,
                    json={
                        "query": project_mutation,
                        "variables": {"name": f"{product_name} Roadmap", "teamIds": [team_id]},
                    },
                    headers=headers,
                )
                proj_resp.raise_for_status()
                proj_data = proj_resp.json().get("data", {}).get("projectCreate", {})
                project = proj_data.get("project", {})
                project_id = project.get("id")

                # Step 3: create one issue per quarter theme
                created_issues = []
                issue_mutation = """
                mutation CreateIssue($title: String!, $teamId: String!, $projectId: String) {
                  issueCreate(input: { title: $title, teamId: $teamId, projectId: $projectId }) {
                    success
                    issue { id identifier title url }
                  }
                }
                """
                num_quarters = int(quarters)
                for i in range(num_quarters):
                    theme = theme_list[i] if i < len(theme_list) else f"Quarter {i+1}"
                    title = f"Q{i+1} — {theme}: {product_name} milestones"
                    iss_resp = await _http.post(
                        graphql_url,
                        json={
                            "query": issue_mutation,
                            "variables": {"title": title, "teamId": team_id, "projectId": project_id},
                        },
                        headers=headers,
                    )
                    iss_resp.raise_for_status()
                    iss = iss_resp.json().get("data", {}).get("issueCreate", {}).get("issue", {})
                    created_issues.append({"quarter": f"Q{i+1}", "theme": theme, "linear_id": iss.get("identifier"), "url": iss.get("url")})

                return json.dumps({
                    "product": product_name,
                    "quarters": num_quarters,
                    "linear_project": {"id": project_id, "name": project.get("name"), "url": project.get("url")},
                    "roadmap_issues": created_issues,
                    "framework": "Theme → Epic → Feature → User Story → Task",
                    "prioritization": "RICE scoring (Reach × Impact × Confidence / Effort)",
                    "source": "linear",
                })
        except Exception as exc:
            logger.warning("Linear create_product_roadmap failed: %s", exc)

    # Stub fallback
    return json.dumps({
        "product": product_name,
        "quarters": int(quarters),
        "roadmap": {f"Q{i+1}": {"theme": theme_list[i] if i < len(theme_list) else f"Quarter {i+1}",
                                   "focus": f"Define key features and milestones for {theme_list[i] if i < len(theme_list) else f'Q{i+1}'}"}
                    for i in range(int(quarters))},
        "framework": "Theme → Epic → Feature → User Story → Task",
        "prioritization": "RICE scoring (Reach × Impact × Confidence / Effort)",
    })



async def _prioritize_features(features: str, method: str = "rice") -> str:
    """Run RICE/ICE scoring on feature candidates."""
    feature_list = [f.strip() for f in features.split(",")]

    if settings.linear_api_key:
        graphql_url = "https://api.linear.app/graphql"
        headers = {
            "Authorization": settings.linear_api_key,
            "Content-Type": "application/json",
        }
        # Query existing Linear issues whose titles match the requested features
        try:
            issues_resp = await _http.post(
                graphql_url,
                json={
                    "query": """
                    {
                      issues(first: 100, orderBy: priority) {
                        nodes {
                          id
                          identifier
                          title
                          priority
                          estimate
                          url
                          state { name }
                          labels { nodes { name } }
                        }
                      }
                    }
                    """
                },
                headers=headers,
            )
            issues_resp.raise_for_status()
            all_issues = issues_resp.json().get("data", {}).get("issues", {}).get("nodes", [])

            # Linear priority: 0=no priority, 1=urgent, 2=high, 3=medium, 4=low
            linear_priority_map = {0: 5, 1: 10, 2: 8, 3: 5, 4: 3}  # map to impact score
            linear_priority_label = {0: "none", 1: "urgent", 2: "high", 3: "medium", 4: "low"}

            # Match requested features to Linear issues (fuzzy title match)
            scored = []
            matched_ids: set = set()
            for i, feature in enumerate(feature_list):
                match = next(
                    (iss for iss in all_issues
                     if feature.lower() in iss["title"].lower() and iss["id"] not in matched_ids),
                    None,
                )
                if match:
                    matched_ids.add(match["id"])
                    pri = match.get("priority", 0)
                    impact = linear_priority_map.get(pri, 5)
                    effort = match.get("estimate") or 5  # story points → effort proxy
                    confidence = 80  # default
                    reach = 1000  # placeholder weekly reach
                    if method == "rice":
                        score = round((reach * impact * confidence / 100) / max(effort, 1), 1)
                        scored.append({
                            "feature": feature,
                            "linear_id": match.get("identifier"),
                            "linear_url": match.get("url"),
                            "linear_priority": linear_priority_label.get(pri, "none"),
                            "reach": reach,
                            "impact": impact,
                            "confidence": confidence,
                            "effort": effort,
                            "rice_score": score,
                        })
                    else:
                        ease = max(10 - effort, 1)
                        score = round(impact * confidence / 100 * ease, 1)
                        scored.append({
                            "feature": feature,
                            "linear_id": match.get("identifier"),
                            "linear_url": match.get("url"),
                            "linear_priority": linear_priority_label.get(pri, "none"),
                            "impact": impact,
                            "confidence": confidence,
                            "ease": ease,
                            "ice_score": score,
                        })
                else:
                    # Feature not yet in Linear — placeholder scores
                    if method == "rice":
                        scored.append({"feature": feature, "linear_id": None, "reach": "TBD", "impact": "TBD", "confidence": "TBD", "effort": "TBD", "rice_score": "not in Linear"})
                    else:
                        scored.append({"feature": feature, "linear_id": None, "impact": "TBD", "confidence": "TBD", "ease": "TBD", "ice_score": "not in Linear"})

            # Sort by score descending
            score_key = "rice_score" if method == "rice" else "ice_score"
            scored.sort(key=lambda x: x.get(score_key, 0) if isinstance(x.get(score_key), (int, float)) else -1, reverse=True)
            for rank, item in enumerate(scored, 1):
                item["rank"] = rank

            return json.dumps({
                "method": method,
                "features": scored,
                "source": "linear",
                "note": "Scores derived from Linear issue priority and estimate fields.",
            })
        except Exception as exc:
            logger.warning("Linear prioritize_features failed: %s", exc)

    # Stub fallback
    scored = []
    for i, feature in enumerate(feature_list):
        if method == "rice":
            scored.append({"feature": feature, "reach": "TBD", "impact": "TBD", "confidence": "TBD", "effort": "TBD", "rice_score": "Calculate: (R×I×C)/E", "rank": i + 1})
        else:
            scored.append({"feature": feature, "impact": "TBD", "confidence": "TBD", "ease": "TBD", "ice_score": "Calculate: I×C×E", "rank": i + 1})
    return json.dumps({"method": method, "features": scored, "note": "Fill in scores (1-10) to rank. Higher score = higher priority."})



async def _generate_user_stories(epic: str, persona: str = "", acceptance_criteria: str = "") -> str:
    """Generate agile user stories with acceptance criteria."""
    return json.dumps({
        "epic": epic,
        "persona": persona or "End User",
        "stories": [
            {"story": f"As a {persona or 'user'}, I want to [action] so that [benefit]",
             "acceptance_criteria": ["Given [context], When [action], Then [expected result]"],
             "story_points": "Estimate during sprint planning",
             "priority": "Must have / Should have / Nice to have"},
        ],
        "template": "As a [persona], I want [action] so that [benefit]",
        "ac_template": "Given [context], When [action], Then [expected result]",
    })



async def _competitive_feature_matrix(product: str, competitors: str) -> str:
    """Map features vs competitors."""
    comp_list = [c.strip() for c in competitors.split(",")]
    return json.dumps({
        "product": product,
        "competitors": comp_list,
        "matrix_template": {
            "columns": [product] + comp_list,
            "row_categories": ["Core Features", "Integrations", "Pricing", "Support", "Security", "Mobile"],
            "scoring": "Has | Partial | Missing | Best-in-class",
        },
        "analysis_areas": ["Feature parity gaps", "Unique differentiators", "Table-stakes features", "Future opportunities"],
    })



def register_product_tools(registry):
    """Register all product tools with the given registry."""
    from models import ToolParameter

    registry.register("create_product_roadmap", "Generate product roadmap with quarterly themes and milestones.",
        [ToolParameter(name="product_name", description="Product name"),
         ToolParameter(name="quarters", description="Number of quarters to plan", required=False),
         ToolParameter(name="themes", description="Comma-separated quarter themes", required=False)],
        _create_product_roadmap, "product")

    registry.register("prioritize_features", "Run RICE or ICE scoring on feature candidates for data-driven prioritization.",
        [ToolParameter(name="features", description="Comma-separated feature names"),
         ToolParameter(name="method", description="Scoring method: rice or ice", required=False)],
        _prioritize_features, "product")

    registry.register("generate_user_stories", "Generate agile user stories with acceptance criteria from an epic.",
        [ToolParameter(name="epic", description="Epic or feature description"),
         ToolParameter(name="persona", description="User persona", required=False),
         ToolParameter(name="acceptance_criteria", description="Key acceptance criteria", required=False)],
        _generate_user_stories, "product")

    registry.register("competitive_feature_matrix", "Map features vs competitors to identify gaps and differentiators.",
        [ToolParameter(name="product", description="Your product name"),
         ToolParameter(name="competitors", description="Comma-separated competitor names")],
        _competitive_feature_matrix, "product")

    # ── Partnership, UGC & Lobbying Tools ──

