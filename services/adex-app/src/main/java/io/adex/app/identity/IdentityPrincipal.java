package io.adex.app.identity;

import java.util.UUID;

/** Authenticated identity, deliberately independent of cookies and servlet responses. */
public record IdentityPrincipal(UUID id, String username, boolean guest) {}
