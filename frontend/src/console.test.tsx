// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Badge, Console, Setup } from "./main";

beforeEach(() =>
  vi.stubGlobal("localStorage", {
    getItem: () => null,
    setItem: () => {},
    removeItem: () => {},
  }),
);
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("setup wizard", () => {
  it("keeps an invalid bootstrap token on Welcome", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        json: async () => ({
          error: { message: "Bootstrap token missing or incorrect" },
        }),
      })),
    );
    render(<Setup onDone={() => {}} />);
    fireEvent.change(screen.getByLabelText("Bootstrap token"), {
      target: { value: "wrong-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Bootstrap token missing or incorrect",
    );
    expect(
      screen.getByRole("heading", { name: "Welcome to NotiDeck" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Connect your database" }),
    ).not.toBeInTheDocument();
  });

  it("requires local token, tests database and checks password confirmation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ connected: true }),
      })),
    );
    render(<Setup onDone={() => {}} />);
    expect(
      screen.getByRole("heading", { name: "Welcome to NotiDeck" }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Bootstrap token"), {
      target: { value: "  local-token  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(
      await screen.findByRole("heading", { name: "Connect your database" }),
    ).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/setup/verify",
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Bootstrap-Token": "local-token",
        }),
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Test the database connection",
    );
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await screen.findByRole("button", { name: "Connection verified" });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(
      screen.getByRole("heading", { name: "Create your administrator" }),
    ).toBeInTheDocument();
  });
});

describe("console permissions and navigation", () => {
  it("renders readable states", () => {
    render(<Badge value="RETRY_SCHEDULED" />);
    expect(screen.getByText("RETRY SCHEDULED")).toBeInTheDocument();
  });
  it("hides administrative controls for viewers and opens notification history", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => ({
        ok: true,
        json: async () =>
          url.includes("dashboard")
            ? {
                notifications: 0,
                deliveries: {},
                severity: {},
                channels: 0,
                recent: [],
              }
            : { items: [], total: 0 },
      })),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <Console
          user={{ full_name: "Read Only", role: "VIEWER" }}
          onLogout={() => {}}
        />
      </QueryClientProvider>,
    );
    expect(
      screen.queryByRole("button", { name: "Users" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Settings" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Notifications" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: /Create/ }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Search notifications")).toBeInTheDocument();
    queryClient.clear();
  });
});
