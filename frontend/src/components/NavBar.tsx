"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

const LINKS = [
  { href: "/jobs", label: "JD & năng lực" },
  { href: "/cv", label: "Chấm CV" },
  { href: "/interviews", label: "Phỏng vấn thử" },
];

export function NavBar() {
  const { user, signOut } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-bold text-indigo-700">
          TalentCompass
        </Link>
        {user && (
          <nav className="flex flex-wrap gap-4 text-sm">
            {LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={pathname.startsWith(l.href) ? "font-semibold text-indigo-700" : "text-slate-600 hover:text-slate-900"}
              >
                {l.label}
              </Link>
            ))}
          </nav>
        )}
        <div className="ml-auto flex items-center gap-3 text-sm">
          {user ? (
            <>
              <span className="text-slate-600">
                {user.full_name} · <span className="uppercase">{user.role}</span>
              </span>
              <button
                className="btn-ghost px-3 py-1"
                onClick={() => {
                  signOut();
                  router.push("/");
                }}
              >
                Đăng xuất
              </button>
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
}
