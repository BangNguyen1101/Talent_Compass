"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { navFor, ROLE_LABEL } from "@/lib/roles";

export function NavBar() {
  const { user, signOut } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-bold text-indigo-700">
          TalentCompass
        </Link>
        {user && (
          <nav className="flex flex-wrap gap-4 text-sm">
            {navFor(user.role).map((l) => (
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
        {user && (
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-slate-600">
              {user.full_name} · <span className="font-medium">{ROLE_LABEL[user.role]}</span>
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
          </div>
        )}
      </div>
    </header>
  );
}
