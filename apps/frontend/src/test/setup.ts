import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// `test.globals` is off (explicit imports preferred), so React Testing Library's own
// auto-cleanup — which detects a global `afterEach` — never registers. Do it explicitly,
// otherwise each test's DOM leaks into the next and queries start matching duplicates.
afterEach(() => cleanup());

// jsdom has no ResizeObserver; EChart relies on one to resize the canvas.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver ??= ResizeObserverStub;
