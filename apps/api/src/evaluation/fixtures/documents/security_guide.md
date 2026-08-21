# Acme Corp Information Security Standards

## 1. Authentication and Session Management
All internal services must enforce JSON Web Token (JWT) based authentication. Access tokens must have a strict expiration time of 15 minutes. Refresh tokens have a maximum lifetime of 7 days and must be stored in secure, HttpOnly, SameSite=Strict cookies to prevent cross-site scripting (XSS) extraction.

## 2. Password Requirements and Multi-Factor Authentication
Passwords must contain a minimum of 8 characters, including at least one uppercase letter, one lowercase letter, one numeric digit, and one special character. Multi-factor authentication (MFA) via TOTP or WebAuthn hardware keys is mandatory for all production system access.

## 3. Cryptographic and Encryption Standards
All sensitive data at rest must be encrypted using AES-256-GCM. All data in transit across public and internal networks must enforce TLS 1.3 encryption. Legacy cryptographic protocols including TLS 1.0, TLS 1.1, SSLv3, and DES/3DES are strictly prohibited across all infrastructure endpoints.

## 4. Rate Limiting and Denial of Service Mitigation
Public API endpoints enforce a global rate limit of 100 requests per minute per IP address. Authenticated users are permitted up to 1,000 requests per minute. Exceeding these limits triggers an HTTP 429 Too Many Requests response with a Retry-After header.
