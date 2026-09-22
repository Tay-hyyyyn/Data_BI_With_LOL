import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../test/server";
import { apiGet, ApiError } from "./apiClient";

describe("apiGet", () => {
  it("resolves with the parsed JSON body on success", async () => {
    server.use(http.get("/api/v1/probe", () => HttpResponse.json({ ok: true })));
    await expect(apiGet<{ ok: boolean }>("/api/v1/probe")).resolves.toEqual({ ok: true });
  });

  it("throws an ApiError carrying the status and the backend's detail message", async () => {
    server.use(
      http.get("/api/v1/probe", () =>
        HttpResponse.json({ detail: "존재하지 않는 컬럼: x" }, { status: 422 }),
      ),
    );
    await expect(apiGet("/api/v1/probe")).rejects.toMatchObject({
      status: 422,
      message: "존재하지 않는 컬럼: x",
    });
  });

  it("falls back to a generic message when the error body is not JSON", async () => {
    server.use(
      http.get("/api/v1/probe", () => new HttpResponse("<html>502</html>", { status: 502 })),
    );
    const error = await apiGet("/api/v1/probe").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("요청을 처리하지 못했습니다.");
  });
});
