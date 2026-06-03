import "./globals.css";

export const metadata = {
  title: "StockBoard — US Market Watchlist",
  description: "A clean real-time US stock watchlist dashboard powered by Finnhub.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
