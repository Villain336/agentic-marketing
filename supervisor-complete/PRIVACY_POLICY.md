# Omni OS — Privacy Policy

**Effective Date:** [INSERT DATE BEFORE LAUNCH]
**Last Updated:** 2026-03-20

## 1. Introduction

This Privacy Policy describes how Omni OS ("we", "us", "the Service") collects, uses, stores, and protects your personal information. We are committed to GDPR, CCPA, and applicable privacy law compliance.

## 2. Data Controller

Omni OS operates as the data controller for user account information and as a data processor for campaign data processed by AI agents on your behalf.

## 3. Information We Collect

### 3.1 Account Information
- Email address and name (registration)
- Authentication tokens (Supabase Auth, JWT)
- Subscription tier and billing status
- Stripe customer ID (payment processing)

### 3.2 Campaign Data (User-Provided)
- Business name, service description, and ideal customer profile
- Marketing content, outreach templates, and campaign configurations
- Prospect lists and contact information you upload
- API keys and credentials for third-party integrations

### 3.3 Service-Generated Data
- Agent execution logs (inputs, outputs, tool calls, durations)
- Campaign performance metrics and scoring
- Spend tracking and budget utilization
- Approval queue decisions and audit trail

### 3.4 Technical Data
- IP address (logged for security and rate limiting)
- Browser user agent (for session management)
- Request metadata (method, path, status code, duration)

## 4. How We Use Your Data

| Purpose | Legal Basis (GDPR) |
|---------|-------------------|
| Provide the Service (run AI agents, manage campaigns) | Contract performance |
| Process payments via Stripe | Contract performance |
| Send transactional emails (account, billing) | Legitimate interest |
| Monitor service health and security | Legitimate interest |
| Improve AI agent performance and quality | Legitimate interest |
| Comply with legal obligations (tax, audit) | Legal obligation |

## 5. Data Sharing with Third Parties

### 5.1 AI/LLM Providers
Campaign data is processed by AI model providers (Anthropic, OpenAI, Google, AWS Bedrock) to power agent execution. **Before transmission, the following PII is automatically redacted:**

- Email addresses → `[EMAIL_REDACTED]`
- Phone numbers → `[PHONE_REDACTED]`
- Social Security Numbers → `[SSN_REDACTED]`
- Credit card numbers → `[CC_REDACTED]`
- IP addresses → `[IP_REDACTED]`
- Street addresses → `[ADDRESS_REDACTED]`
- Dates of birth → `[DOB_REDACTED]`
- API keys → `[API_KEY_REDACTED]`

If PII scrubbing fails for any reason, the request is **blocked** (fail-closed behavior).

### 5.2 Payment Processing
Stripe processes payment information. We do not store credit card numbers. See [Stripe's Privacy Policy](https://stripe.com/privacy).

### 5.3 Third-Party Integrations
When you connect third-party services (SendGrid, Apollo, LinkedIn, etc.), data is shared with those services per your configuration. You are responsible for reviewing their privacy policies.

### 5.4 We Do NOT
- Sell your personal data to third parties
- Use your campaign data for advertising
- Share your data with other users (tenant isolation enforced)
- Train AI models on your data (we use commercial API access only)

## 6. Data Retention

| Data Type | Retention Period |
|-----------|-----------------|
| Account information | Duration of account + 30 days |
| Campaign data | Duration of account + 30 days |
| Agent execution logs | 90 days |
| Audit trail / compliance logs | 1 year |
| Payment records | 7 years (legal requirement) |
| Deleted account data | Purged within 30 days of deletion request |

## 7. Your Rights

### 7.1 GDPR Rights (EU/EEA Residents)
- **Access:** Request a copy of your data (`GET /compliance/export`)
- **Rectification:** Update your account information via Settings
- **Erasure:** Request deletion of all your data (`DELETE /compliance/erase`)
- **Portability:** Export your data in JSON format
- **Restriction:** Request we limit processing of your data
- **Objection:** Object to processing based on legitimate interest
- **Withdraw consent:** Where processing is based on consent, withdraw at any time

### 7.2 CCPA Rights (California Residents)
- **Right to Know:** Request disclosure of data collected about you
- **Right to Delete:** Request deletion of your personal information
- **Right to Opt-Out:** Opt out of the sale of personal information (we do not sell data)
- **Non-Discrimination:** We will not discriminate against you for exercising your rights

### 7.3 How to Exercise Your Rights
- **Self-service:** Use the Settings and Compliance pages in the Service dashboard
- **API:** Use `GET /compliance/export` and `DELETE /compliance/erase` endpoints
- **Email:** Contact privacy@[YOUR-DOMAIN].com

We will respond to rights requests within 30 days (GDPR) or 45 days (CCPA).

## 8. Data Security

We implement the following security measures:

- **Encryption in transit:** TLS 1.2+ on all connections
- **Encryption at rest:** AWS KMS for database, AES-256 for S3 buckets
- **Access control:** Role-based access control (RBAC) with 5-tier permission hierarchy
- **Authentication:** Supabase JWT with httpOnly, secure, samesite=strict cookies
- **Rate limiting:** Per-endpoint, per-provider, and per-tool sliding windows
- **Prompt injection protection:** All tool outputs scanned before entering AI agent loop
- **Webhook verification:** HMAC-SHA256 signature validation
- **PII scrubbing:** Automated before any data is sent to external AI providers
- **Audit logging:** All access and modifications are logged with user attribution
- **Network isolation:** Kubernetes network policies, WAF, security groups
- **Container security:** Non-root processes, Pod Security Admission

## 9. International Data Transfers

Data may be transferred to and processed in the United States. For EU/EEA users, we rely on:

- Standard Contractual Clauses (SCCs) where applicable
- Data processing agreements with sub-processors (AI providers, Stripe)

## 10. Cookies

The Service uses a single essential cookie:

| Cookie | Purpose | Type | Duration |
|--------|---------|------|----------|
| `omni_session` | Authentication session token | Essential (httpOnly, secure, samesite=strict) | 24 hours |

We do not use advertising or tracking cookies. Analytics (if enabled) use privacy-respecting tools.

## 11. Children's Privacy

The Service is not directed at children under 16. We do not knowingly collect personal information from children. If we discover such data has been collected, we will delete it promptly.

## 12. Data Breach Notification

In the event of a personal data breach:

- We will notify affected users within 72 hours (per GDPR Article 33)
- We will notify relevant supervisory authorities as required by law
- Notification will include the nature of the breach, data affected, and remediation steps

## 13. Changes to This Policy

We may update this Privacy Policy from time to time. Material changes will be communicated via email or in-app notification at least 30 days before taking effect.

## 14. Contact

**Data Protection Inquiries:**
- Email: privacy@[YOUR-DOMAIN].com
- Data Protection Officer: dpo@[YOUR-DOMAIN].com

**Supervisory Authority:**
EU residents may lodge a complaint with their local data protection authority.
