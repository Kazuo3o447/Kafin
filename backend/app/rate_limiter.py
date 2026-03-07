"""
rate_limiter — Zentraler Rate-Limiter für alle externen APIs

Input:  API Name und Request Parameter
Output: Steuert das Timing der Requests
Deps:   config, redis
Config: apis.yaml (Rate Limits)
API:    Keine
"""
