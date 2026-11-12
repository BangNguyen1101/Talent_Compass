import type { Metadata } from "next";
import { Be_Vietnam_Pro } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { NavBar } from "@/components/NavBar";
import { ModeBanner } from "@/components/ModeBanner";

const font = Be_Vietnam_Pro({
  variable: "--font-be-vietnam",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "TalentCompass",
  description: "Chấm CV, luyện phỏng vấn và xây khung năng lực bằng AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className={`${font.variable} font-sans antialiased`}>
        <AuthProvider>
          <ModeBanner />
          <NavBar />
          <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
