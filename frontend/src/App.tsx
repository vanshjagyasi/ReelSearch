import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ReelDetail from "./pages/ReelDetail";
import SearchResults from "./pages/SearchResults";
import Entities from "./pages/Entities";
import EntityDetail from "./pages/EntityDetail";
import Share from "./pages/Share";

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Protected routes */}
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="reels/:id" element={<ReelDetail />} />
          <Route path="search" element={<SearchResults />} />
          <Route path="entities" element={<Entities />} />
          <Route path="entities/:id" element={<EntityDetail />} />
          <Route path="share" element={<Share />} />
        </Route>
      </Route>
    </Routes>
  );
}
