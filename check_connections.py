"""
Soulplace Help Desk – check all routes and API connections.
Run from project root: python check_connections.py
"""
import sys

def main():
    # Import app after we're in the right context
    try:
        from app import app
    except Exception as e:
        print("FAIL: Could not import app:", e)
        return 1

    client = app.test_client()
    prefix = "/soulplace"
    ok = 0
    fail = 0

    def get(path, expect_redirect_to_login=False, expect_status=200):
        r = client.get(path, follow_redirects=False)
        if expect_redirect_to_login:
            return r.status_code in (301, 302) and (prefix + "/login" in (r.headers.get("Location") or ""))
        return r.status_code == expect_status

    def post(path, json_body=None, expect_status=200):
        r = client.post(path, json=json_body or {}, content_type="application/json" if json_body else None)
        return r.status_code == expect_status

    # Root "/" redirects to main.login; on Flask that may be "/soulplace/login" (blueprint)
    def root_redirects():
        r = client.get("/", follow_redirects=False)
        loc = r.headers.get("Location") or ""
        return r.status_code in (301, 302) and ("/login" in loc or "soulplace" in loc)

    checks = [
        ("GET  /  (root -> login)", root_redirects),
        ("GET  " + prefix + "/  (index -> login)", lambda: get(prefix + "/", expect_redirect_to_login=True)),
        ("GET  " + prefix + "/login", lambda: get(prefix + "/login")),
        ("GET  " + prefix + "/table", lambda: get(prefix + "/table")),
        ("GET  " + prefix + "/table?table=1", lambda: get(prefix + "/table?table=1")),
        ("GET  " + prefix + "/tables", lambda: get(prefix + "/tables")),
        ("GET  " + prefix + "/links", lambda: get(prefix + "/links")),
        ("GET  " + prefix + "/qr/1", lambda: get(prefix + "/qr/1")),
        ("GET  " + prefix + "/dashboard (no login -> redirect)", lambda: get(prefix + "/dashboard", expect_redirect_to_login=True)),
        ("GET  " + prefix + "/api/requests (no login -> redirect)", lambda: get(prefix + "/api/requests", expect_redirect_to_login=True)),
        ("POST " + prefix + "/api/request/create", lambda: post(prefix + "/api/request/create", json_body={"table": 1, "note": "connection-check"}, expect_status=200)),
    ]

    print("Soulplace Help Desk - connection check")
    print("=" * 50)
    for name, check in checks:
        try:
            if check():
                print("  OK   " + name)
                ok += 1
            else:
                print("  FAIL " + name)
                fail += 1
        except Exception as e:
            print("  FAIL " + name + "  [" + str(e) + "]")
            fail += 1
    print("=" * 50)
    print("  Result: %d OK, %d FAIL" % (ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
