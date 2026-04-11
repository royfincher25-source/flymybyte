# FlyMyByte Requirements

> **Version:** 1.0
> **Created:** 2026-04-11

---

## Functional Requirements

### Core Features
- **FR-1:** VPN tunnel enable/disable via web UI
- **FR-2:** Domain bypass list management (add/remove/activate)
- **FR-3:** DNS-based traffic routing for specific domains
- **FR-4:** Configuration backup and restore
- **FR-5:** Router firmware version checking
- **FR-6:** System restart and service management

### Authentication
- **FR-7:** Password-based login authentication
- **FR-8:** CSRF token protection for all POST requests
- **FR-9:** Session management with timeout

### Configuration
- **FR-10:** Environment-based configuration via .env file
- **FR-11:** Singleton WebConfig with thread safety
- **FR-12:** Configuration backup system

---

## Non-Functional Requirements

### Performance
- **NFR-1:** RAM usage < 100MB
- **NFR-2:** CPU usage < 20%
- **NFR-3:** Response time < 2 seconds

### Reliability
- **NFR-4:** Graceful error handling with logging
- **NFR-5:** Service operation fallback to shell
- **NFR-6:** Startup warnings for non-critical failures

### Security
- **NFR-7:** Timing-safe password comparison
- **NFR-8:** Session secret key required
- **NFR-9:** No hardcoded credentials

### Compatibility
- **NFR-10:** Keenetic OS (embedded Linux)
- **NFR-11:** Python 3.x
- **NFR-12:** Flask 3.0+

---

## Technical Requirements

### System Dependencies
- Python 3 with Flask, requests, waitress
- iptables (routing rules)
- dnsmasq (DNS routing)
- ipset (IP collections)
- xray (VPN tunnel)

### Router Requirements
- SSH access for deployment
- /opt/etc/ directory for config
- Persistent storage for bypass lists
- Web UI accessible on local network

---

## Refactoring Goals

### Code Quality
- **RG-1:** services.py < 1000 lines (from 1553)
- **RG-2:** constants.py < 250 lines (from 301)
- **RG-3:** No duplication in route handlers
- **RG-4:** All shell fallbacks have Python equivalents

### Maintainability
- **RG-5:** Modular parser system (VLESS, Shadowsocks, Trojan)
- **RG-6:** Manager classes for each domain
- **RG-7:** Clean separation: routes / core / views

### Documentation
- **RG-8:** Complete codebase analysis
- **RG-9:** Refactoring roadmap with phases
- **RG-10:** Architecture documentation

---

## Acceptance Criteria

- [ ] All 12 functional requirements implemented
- [ ] All 12 non-functional requirements met
- [ ] Router testing passes for all phases
- [ ] services.py line count < 1000
- [ ] constants.py line count < 250
- [ ] No duplicate logic in routes
- [ ] Phase 3 (DNS merge) tested and stable