import { Routes, Route } from "react-router";
import { ResetPasswordForm } from "@/components/ResetPasswordForm";
import { VerifyEmailClient } from "@/components/VerifyEmailClient";
import { AuthLayout } from "@/layouts/AuthLayout";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import LoginPage from "@/pages/auth/LoginPage";
import SignupPage from "@/pages/auth/SignupPage";
import ForgotPasswordPage from "@/pages/auth/ForgotPasswordPage";
import DashboardPage from "@/pages/dashboard/DashboardPage";
import MessagesPage from "@/pages/dashboard/MessagesPage";
import MessageDetailPage from "@/pages/dashboard/MessageDetailPage";
import ChannelsPage from "@/pages/dashboard/ChannelsPage";
import RulesPage from "@/pages/dashboard/RulesPage";
import IngestEndpointsPage from "@/pages/dashboard/IngestEndpointsPage";
import AccountPage from "@/pages/dashboard/AccountPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordForm token={null} />} />
        <Route path="/verify-email" element={<VerifyEmailClient token={null} />} />
      </Route>
      <Route element={<DashboardLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/messages" element={<MessagesPage />} />
        <Route path="/messages/:id" element={<MessageDetailPage />} />
        <Route path="/channels" element={<ChannelsPage />} />
        <Route path="/rules" element={<RulesPage />} />
        <Route path="/ingest-endpoints" element={<IngestEndpointsPage />} />
        <Route path="/account" element={<AccountPage />} />
      </Route>
    </Routes>
  );
}
