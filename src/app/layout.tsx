import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";
import { cookies } from "next/headers";

export const metadata: Metadata = {
  title: "Financial Dashboard",
  description: "Personal portfolio intelligence powered by Claude",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const isAuth = !!cookieStore.get("fin_session")?.value;

  return (
    <html lang="en" className="dark">
      <body className="bg-[#1a1a2e] text-gray-200 antialiased">
        {isAuth ? (
          <div className="flex min-h-screen">
            <Sidebar />
            {/* Push content right of sidebar */}
            <main className="flex-1 ml-56 lg:ml-64 min-h-screen">
              {children}
            </main>
          </div>
        ) : (
          // Auth pages: no sidebar
          <>{children}</>
        )}
      </body>
    </html>
  );
}
