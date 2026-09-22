import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppProviders } from "./providers";
import { router } from "./router";

// This is a real end-to-end mount (router + react-query + msw-mocked fetch), and the module
// graph (echarts, react-router, react-query) is cold on first run — give it more than the
// default 1000ms before treating a missing element as a real failure.
const LONG_TIMEOUT = { timeout: 5_000 };

describe("app shell", () => {
  it("loads the dataset list, selects the first one and renders its KPIs on the data hub", async () => {
    render(
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>,
    );

    // Sidebar: the dataset from the mocked GET /api/v1/datasets appears and is auto-selected.
    // (Queried by role, not text: the data hub's <h1> also shows the dataset name verbatim.)
    expect(await screen.findByRole("button", { name: /마케팅 캠페인/ }, LONG_TIMEOUT)).toHaveClass(
      "selected",
    );

    // Data hub: KPIs render from the mocked profile, and version_number (not a hardcoded "v1") shows through.
    expect(await screen.findByText("2,000", {}, LONG_TIMEOUT)).toBeInTheDocument();
    expect(await screen.findByText("v3", {}, LONG_TIMEOUT)).toBeInTheDocument();
  });

  it("navigates to the LoL studio and shows the private-data notice", async () => {
    render(
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>,
    );

    await userEvent.click(await screen.findByRole("link", { name: /LoL 실험실/ }, LONG_TIMEOUT));
    expect(await screen.findByText("개발 데이터 보호 적용", {}, LONG_TIMEOUT)).toBeInTheDocument();
  });
});
