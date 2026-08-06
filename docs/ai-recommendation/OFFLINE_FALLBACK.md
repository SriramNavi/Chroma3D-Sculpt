# Offline Fallback

No key, network, or provider is required for Chroma3D's existing functionality. After a current Sprint 6 ranking exists, **Offline Sprint 6 View** projects its highest locally feasible safe-default item through the same recommendation model without pretending AI was used.

Offline items set `provider_generated=false`, retain Sprint 6 bounded-search limitations, cannot create a candidate or parameter, and follow the same selection, preview, approval and workspace rules. A missing eligible target yields a truthful `CANNOT_RECOMMEND` result. Provider outage never triggers an automatic fallback or provider switch; the user chooses the offline action explicitly.
