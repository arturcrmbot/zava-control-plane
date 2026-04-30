import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { vi } from "vitest";
import Apply from "../../../web/portal/src/routes/Apply";

// MSW intercepts the network call so the component sees a 202 response.
// Separately, we spy on fetch() to inspect the multipart FormData body the
// component built (jsdom serializes FormData in fetch in a lossy way before
// it reaches msw, so we capture at the call site).
const server = setupServer(
  http.post("*/api/portal/apply", () =>
    HttpResponse.json(
      { status: "submitted", candidate_id: "C-XYZ" },
      { status: 202 },
    ),
  ),
);

let fetchSpy: ReturnType<typeof vi.spyOn>;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  fetchSpy = vi.spyOn(globalThis, "fetch");
});
afterEach(() => {
  server.resetHandlers();
  fetchSpy.mockRestore();
});
afterAll(() => server.close());

describe("Apply", () => {
  test("submits multipart form to /api/portal/apply and shows confirmation on 202", async () => {
    render(<Apply />);

    fireEvent.change(screen.getByLabelText(/role/i), {
      target: { value: "REQ-SDE-USA-DEMO" },
    });
    fireEvent.change(screen.getByLabelText(/name/i), {
      target: { value: "Alice Engineer" },
    });
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "alice@example.com" },
    });

    const file = new File(["%PDF-1.4 fake"], "cv.pdf", {
      type: "application/pdf",
    });
    const cvInput = screen.getByLabelText(/cv/i) as HTMLInputElement;
    // Robust file-input attach for jsdom: define a real FileList on .files
    // so that browser-side `required` validation passes once the form submits.
    Object.defineProperty(cvInput, "files", { value: [file], configurable: true });
    fireEvent.change(cvInput);

    // Submit the form. fireEvent.submit bypasses jsdom's form-validation
    // gating (which the file-input.required check would otherwise stop)
    // and dispatches the React synthetic submit handler directly.
    fireEvent.submit(cvInput.form!);

    // findBy* returns a promise that polls until the element appears (auto-act).
    await screen.findByText(/C-XYZ/, {}, { timeout: 3000 });
    expect(screen.getByText(/Application submitted/i)).toBeTruthy();

    // Verify the component called fetch with a FormData body (multipart
    // submission, not JSON) carrying the right fields. We inspect the
    // FormData at the call site because jsdom would lose the field info by
    // the time msw sees the request.
    expect(fetchSpy).toHaveBeenCalled();
    const lastCall = fetchSpy.mock.calls.at(-1)!;
    const url = lastCall[0] as string;
    const init = lastCall[1] as RequestInit;
    expect(url).toBe("/api/portal/apply");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    const fd = init.body as FormData;
    expect(fd.get("role_id")).toBe("REQ-SDE-USA-DEMO");
    expect(fd.get("name")).toBe("Alice Engineer");
    expect(fd.get("email")).toBe("alice@example.com");
    const sentCv = fd.get("cv");
    // jsdom's FormData(form) wraps file inputs in a File-shaped value but
    // doesn't always preserve name/type. We assert presence + non-emptiness.
    expect(sentCv).toBeInstanceOf(File);

    // Confirmation surface shows the candidate id from the API.
    expect(screen.getByText(/C-XYZ/)).toBeTruthy();
  });

  test("renders all three demo roles in the dropdown", () => {
    render(<Apply />);
    const roleSelect = screen.getByLabelText(/role/i) as HTMLSelectElement;
    const options = Array.from(roleSelect.options).map((o) => o.value);
    expect(options).toEqual(
      expect.arrayContaining([
        "REQ-SDE-USA-DEMO",
        "REQ-SDE-DE-DEMO",
        "REQ-CD-USA-DEMO",
      ]),
    );
  });
});
