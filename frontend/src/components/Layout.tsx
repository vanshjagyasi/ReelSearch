import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Home, Search, Tag, Plus, LogOut, User } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import SaveReelModal from "./SaveReelModal";

const navItems = [
  { to: "/", icon: Home, label: "Home" },
  { to: "/search", icon: Search, label: "Search" },
  { to: "/entities", icon: Tag, label: "Entities" },
];

export default function Layout() {
  const [saveOpen, setSaveOpen] = useState(false);
  const { user, logout } = useAuth();

  const displayLabel = user?.display_name || user?.username || "";

  return (
    <div className="flex min-h-screen flex-col">
      {/* Desktop top nav */}
      <header className="sticky top-0 z-30 hidden border-b border-gray-200 bg-white md:block">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-4">
          <NavLink to="/" className="text-lg font-bold text-indigo-600">
            ReelSearch
          </NavLink>
          <nav className="flex gap-1">
            {navItems.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                    isActive
                      ? "bg-indigo-50 text-indigo-700"
                      : "text-gray-600 hover:bg-gray-100"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="flex-1" />
          <button
            onClick={() => setSaveOpen(true)}
            className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700"
          >
            <Plus size={16} />
            Save Reel
          </button>
          <div className="flex items-center gap-2 border-l border-gray-200 pl-4">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-100 text-indigo-600">
              <User size={14} />
            </div>
            <span className="max-w-[120px] truncate text-sm text-gray-600">
              {displayLabel}
            </span>
            <button
              onClick={logout}
              title="Sign out"
              className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </header>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 md:hidden">
        <span className="text-lg font-bold text-indigo-600">ReelSearch</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSaveOpen(true)}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-600 text-white"
          >
            <Plus size={18} />
          </button>
          <button
            onClick={logout}
            title="Sign out"
            className="flex h-9 w-9 items-center justify-center rounded-full text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 pb-20 pt-4 md:pb-6">
        <Outlet />
      </main>

      {/* Mobile bottom nav */}
      <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-gray-200 bg-white md:hidden">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex flex-1 flex-col items-center gap-0.5 py-2 text-xs transition ${
                isActive ? "text-indigo-600" : "text-gray-500"
              }`
            }
          >
            <Icon size={20} />
            {label}
          </NavLink>
        ))}
      </nav>

      {saveOpen && <SaveReelModal onClose={() => setSaveOpen(false)} />}
    </div>
  );
}
