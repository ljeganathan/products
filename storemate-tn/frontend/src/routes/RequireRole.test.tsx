import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { RequireRole } from "@/routes/RequireRole";
import { useAuthStore } from "@/store/authStore";
import type { AuthUser, UserRole } from "@/types/auth";

function makeUser(role: UserRole): AuthUser {
  return {
    id: "u1",
    tenant_id: role === "product_owner" ? null : "t1",
    store_id: "s1",
    name: "Test User",
    email: "test@example.com",
    phone: null,
    role,
    is_active: true,
    language_pref: "en",
  };
}

function renderWithRole(allow: UserRole[], initialPath = "/protected") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/dashboard" element={<div>Admin home</div>} />
        <Route path="/pos" element={<div>POS home</div>} />
        <Route path="/owner" element={<div>Owner home</div>} />
        <Route element={<RequireRole allow={allow} />}>
          <Route path="/protected" element={<div>Protected content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireRole", () => {
  afterEach(() => {
    useAuthStore.getState().clear();
  });

  it("redirects to /login when no user is signed in", () => {
    renderWithRole(["admin"]);
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("redirects an unauthorized role to their own home screen, not a blank page", () => {
    useAuthStore.setState({ user: makeUser("pos_user") });
    renderWithRole(["admin"]);
    expect(screen.getByText("POS home")).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("renders the protected content for an allowed role", () => {
    useAuthStore.setState({ user: makeUser("admin") });
    renderWithRole(["admin"]);
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });

  it("allows a product_owner into a product_owner-only route", () => {
    useAuthStore.setState({ user: makeUser("product_owner") });
    renderWithRole(["product_owner"]);
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });

  it("allows multiple roles when the route is shared (admin + pos_user)", () => {
    useAuthStore.setState({ user: makeUser("pos_user") });
    renderWithRole(["admin", "pos_user"]);
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });
});
