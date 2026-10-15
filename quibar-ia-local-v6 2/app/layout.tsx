import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Quibar | Tótem interactivo local",
  description: "Demostración táctil privada del tótem Quibar para descubrir PYMEs ficticias de Quilaco y Santa Bárbara.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es-CL">
      <body className="antialiased">{children}</body>
    </html>
  );
}
