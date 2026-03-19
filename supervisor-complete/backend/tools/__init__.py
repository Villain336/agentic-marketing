"""
Tools package — domain-specific tool modules.

Re-exports the ToolRegistry singleton, register_all_tools(), _to_json helper,
and all private handler functions so that existing ``from tools import ...``
statements continue to work.
"""
from __future__ import annotations

from tools.registry import ToolRegistry, _to_json, _http, _http_long  # noqa: F401
from config import settings  # noqa: F401  — backward compat for patch("tools.settings")

# ── Domain register functions ────────────────────────────────────────────────
from tools.ads import register_ads_tools
from tools.advisor import register_advisor_tools
from tools.analytics import register_analytics_tools
from tools.aws import register_aws_tools
from tools.bi import register_bi_tools
from tools.community import register_community_tools
from tools.computer_use import register_computer_use_tools
from tools.content import register_content_tools
from tools.crm import register_crm_tools
from tools.delivery import register_delivery_tools
from tools.deployment import register_deployment_tools
from tools.design import register_design_tools
from tools.development import register_development_tools
from tools.email import register_email_tools
from tools.figma import register_figma_tools
from tools.finance import register_finance_tools
from tools.formation import register_formation_tools
from tools.harvey import register_harvey_tools
from tools.hr import register_hr_tools
from tools.legal import register_legal_tools
from tools.manufacturing import register_manufacturing_tools
from tools.memory import register_memory_tools
from tools.messaging import register_messaging_tools
from tools.nvidia import register_nvidia_tools
from tools.orchestration import register_orchestration_tools
from tools.partnerships import register_partnerships_tools
from tools.pr import register_pr_tools
from tools.procurement import register_procurement_tools
from tools.product import register_product_tools
from tools.prospecting import register_prospecting_tools
from tools.referral import register_referral_tools
from tools.reindustrialization import register_reindustrialization_tools
from tools.reporting import register_reporting_tools
from tools.research import register_research_tools
from tools.sales import register_sales_tools
from tools.security import register_security_tools
from tools.social import register_social_tools
from tools.supervisor import register_supervisor_tools
from tools.support import register_support_tools
from tools.upsell import register_upsell_tools
from tools.voice import register_voice_tools
from tools.website import register_website_tools
from tools.claude_sdk import register_claude_sdk_tools
from tools.crawlers import register_crawler_tools

# ── Singleton registry ───────────────────────────────────────────────────────
registry = ToolRegistry()


def register_all_tools():
    """Register every tool from every domain module."""
    register_ads_tools(registry)
    register_advisor_tools(registry)
    register_analytics_tools(registry)
    register_aws_tools(registry)
    register_bi_tools(registry)
    register_community_tools(registry)
    register_computer_use_tools(registry)
    register_content_tools(registry)
    register_crm_tools(registry)
    register_delivery_tools(registry)
    register_deployment_tools(registry)
    register_design_tools(registry)
    register_development_tools(registry)
    register_email_tools(registry)
    register_figma_tools(registry)
    register_finance_tools(registry)
    register_formation_tools(registry)
    register_harvey_tools(registry)
    register_hr_tools(registry)
    register_legal_tools(registry)
    register_manufacturing_tools(registry)
    register_memory_tools(registry)
    register_messaging_tools(registry)
    register_nvidia_tools(registry)
    register_orchestration_tools(registry)
    register_partnerships_tools(registry)
    register_pr_tools(registry)
    register_procurement_tools(registry)
    register_product_tools(registry)
    register_prospecting_tools(registry)
    register_referral_tools(registry)
    register_reindustrialization_tools(registry)
    register_reporting_tools(registry)
    register_research_tools(registry)
    register_sales_tools(registry)
    register_security_tools(registry)
    register_social_tools(registry)
    register_supervisor_tools(registry)
    register_support_tools(registry)
    register_upsell_tools(registry)
    register_voice_tools(registry)
    register_website_tools(registry)
    register_claude_sdk_tools(registry)
    register_crawler_tools(registry)


# Auto-register all tools on import (matches legacy tools.py behaviour)
register_all_tools()

# ── Re-export all private handler functions for backwards compatibility ──────
# Files like main.py do ``from tools import _generate_cad_model`` etc.
from tools.ads import _create_meta_ad_campaign, _create_google_ads_campaign, _create_linkedin_ad_campaign, _get_ad_performance, _build_landing_page, _setup_conversion_tracking  # noqa: F401
from tools.advisor import _build_financial_model, _tax_strategy_research, _pricing_strategy, _cash_flow_analysis, _growth_playbook  # noqa: F401
from tools.analytics import _get_google_analytics_data, _get_search_console_data, _keyword_planner_lookup, _create_ad_rule  # noqa: F401
from tools.aws import _eks_create_cluster, _eks_deploy_workspace, _sagemaker_train, _sagemaker_deploy_endpoint, _iot_register_device, _iot_send_command, _iot_get_telemetry, _iot_create_rule, _robomaker_create_sim, _robomaker_deploy_robot, _greengrass_deploy_edge, _step_functions_create_workflow, _step_functions_start, _s3_upload, _s3_download  # noqa: F401
from tools.bi import _build_metrics_hierarchy, _build_attribution_model, _build_dashboard_spec, _build_executive_dashboard, _build_agent_data_layer, _create_etl_pipeline, _create_alert_rules  # noqa: F401
from tools.community import _search_reddit, _post_to_reddit, _search_hackernews, _post_to_hackernews, _search_tiktok_trends, _search_youtube_trends  # noqa: F401
from tools.computer_use import _launch_live_browser, _browser_action, _vision_navigate, _vision_plan, _browser_parallel_launch, _browser_request_handoff, _browser_close_session, _browser_get_dashboard, _browser_get_recording, _browser_annotate_recording, _browser_get_stats  # noqa: F401
from tools.content import _seo_keyword_research, _seo_backlink_analysis, _generate_image, _publish_to_cms, _check_plagiarism  # noqa: F401
from tools.crm import _create_crm_contact, _update_deal_stage, _log_crm_activity, _get_pipeline_summary, _create_booking_link  # noqa: F401
from tools.delivery import _build_delivery_sop, _capacity_planning, _build_client_intake, _build_welcome_sequence, _build_deliverable_pipeline, _track_client_milestone, _calculate_client_ltv  # noqa: F401
from tools.deployment import _deploy_to_vercel, _deploy_to_cloudflare, _check_domain_availability, _register_domain, _manage_dns, _setup_analytics, _setup_uptime_monitoring, _take_screenshot, _check_page_speed, _generate_dockerfile, _deploy_to_cloud  # noqa: F401
from tools.design import _generate_logo, _generate_color_palette, _get_font_pairing, _upload_asset  # noqa: F401
from tools.development import _generate_code, _generate_project_scaffold, _generate_api_spec, _generate_database_schema, _run_code_review, _generate_test_suite, _generate_mobile_app, _generate_desktop_app, _generate_browser_extension, _generate_agent_framework, _generate_cli_tool, _generate_microservice  # noqa: F401
from tools.email import _send_email, _schedule_email_sequence, _check_email_status, _check_email_warmup_status, _detect_email_replies, _create_email_list, _add_subscriber, _get_email_analytics  # noqa: F401
from tools.figma import _figma_get_file, _figma_get_components, _figma_get_styles, _figma_export_assets, _figma_extract_design_tokens, _figma_get_team_projects  # noqa: F401
from tools.finance import _generate_chart_of_accounts, _generate_pnl_template, _tax_deadline_calendar, _create_invoice, _create_subscription, _check_payment_status, _send_payment_reminder, _setup_dunning_sequence, _get_revenue_metrics, _tax_writeoff_audit, _reasonable_salary_calculator, _wealth_structure_analyzer, _multi_entity_planner  # noqa: F401
from tools.formation import _research_entity_types, _file_business_entity, _apply_for_ein, _research_registered_agents, _research_business_banking, _research_business_insurance, _research_business_licenses  # noqa: F401
from tools.harvey import _harvey_legal_research, _harvey_contract_analysis, _harvey_regulatory_analysis, _harvey_case_law_search  # noqa: F401
from tools.hr import _create_hiring_plan, _worker_classification_check  # noqa: F401
from tools.legal import _generate_document, _send_for_signature, _research_ip_protection, _employment_law_research, _compliance_checklist, _track_regulation, _generate_compliance_report, _audit_agent_output, _create_policy_document  # noqa: F401
from tools.manufacturing import _generate_cad_model, _optimize_cad_design, _generate_gcode, _slice_3d_print, _control_printer, _control_cnc, _generate_bom, _inspect_part_vision, _generate_pcb_layout, _manage_print_farm, _production_plan, _generate_technical_drawing  # noqa: F401
from tools.memory import _store_data, _read_data  # noqa: F401
from tools.messaging import _send_slack_message, _send_telegram_message  # noqa: F401
from tools.nvidia import _allocate_gpu, _release_gpu, _gpu_cluster_status, _optimize_model_tensorrt, _deploy_model_triton, _triton_infer, _create_digital_twin, _simulate_digital_twin, _create_robot_sim, _train_robot_policy, _run_vision_inspection  # noqa: F401
from tools.orchestration import _compare_campaigns, _clone_campaign_config, _portfolio_dashboard, _provision_agent_workspace, _configure_browser_automation, _create_code_sandbox, _design_workflow, _build_agent_pipeline, _set_autonomy_level, _create_workflow_monitor  # noqa: F401
from tools.partnerships import _identify_partners, _create_ugc_brief, _draft_partnership_agreement, _discover_creators, _industry_association_research  # noqa: F401
from tools.pr import _draft_press_release, _pitch_journalist, _media_monitor  # noqa: F401
from tools.procurement import _compare_tool_pricing, _check_integration_compatibility, _track_tool_spend, _search_suppliers, _send_rfq  # noqa: F401
from tools.product import _create_product_roadmap, _prioritize_features, _generate_user_stories, _competitive_feature_matrix  # noqa: F401
from tools.prospecting import _find_contacts, _verify_email, _enrich_company, _enrich_person, _find_phone_number, _search_linkedin_prospects, _check_buyer_intent, _score_lead  # noqa: F401
from tools.referral import _create_referral_program, _track_referral, _get_referral_metrics, _generate_affiliate_assets  # noqa: F401
from tools.reindustrialization import _analyze_factory_site, _manage_robot_fleet, _reshore_supply_chain, _operate_digital_twin, _optimize_energy, _develop_workforce, _monitor_gov_contracts, _automate_agriculture, _plan_construction, _optimize_logistics, _track_reshoring_metrics, _compliance_check_itar  # noqa: F401
from tools.reporting import _generate_pdf_report, _create_survey  # noqa: F401
from tools.research import _web_search, _web_scrape, _company_research, _analyze_website, _get_market_data, _track_competitor, _run_market_survey, _get_economic_indicators, _get_industry_report, _get_regulatory_updates, _build_knowledge_graph, _create_knowledge_entry, _query_knowledge_base, _track_api_dependency, _calculate_knowledge_coverage, _detect_knowledge_gaps, _build_prediction_model, _build_world_state, _map_social_climate, _build_cultural_calendar, _track_platform_culture, _map_geographic_context, _build_temporal_model, _run_scenario_analysis, _build_sentiment_tracker  # noqa: F401
from tools.sales import _build_sales_pipeline, _generate_discovery_script  # noqa: F401
from tools.security import _run_security_scan, _threat_model, _compliance_audit, _generate_security_report, _answer_security_questionnaire, _red_team_agent, _scan_dependencies, _configure_dlp, _manage_encryption_keys, _incident_response, _monitor_threat_intel, _build_trust_portal  # noqa: F401
from tools.social import _post_twitter, _search_twitter, _post_linkedin, _post_instagram, _schedule_social_post, _get_social_analytics, _monitor_community  # noqa: F401
from tools.supervisor import _get_campaign_dashboard, _trigger_agent_rerun, _send_owner_alert, _get_agent_performance_history  # noqa: F401
from tools.support import _create_support_ticket, _search_knowledge_base, _update_ticket_status, _get_sla_report  # noqa: F401
from tools.upsell import _analyze_expansion_opportunities, _build_qbr_template, _client_health_score  # noqa: F401
from tools.voice import _make_phone_call, _get_call_transcript, _send_sms, _send_linkedin_message  # noqa: F401
from tools.website import _build_full_website, _generate_page  # noqa: F401
from tools.claude_sdk import _claude_generate_code, _claude_review_code, _claude_refactor_code, _claude_explain_code, _claude_generate_tests  # noqa: F401
from tools.crawlers import _crawl_website, _scrape_page, _extract_structured_data, _monitor_competitor  # noqa: F401
