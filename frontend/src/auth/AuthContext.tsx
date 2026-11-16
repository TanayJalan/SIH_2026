import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  getMe,
  login as loginRequest,
  type UserProfile,
} from "../lib/api";

const TOKEN_STORAGE_KEY = "aicte.access_token";
const PROFILE_STORAGE_KEY = "aicte.user_profile";

function readStoredProfile(): UserProfile | null {
  try {
    const raw = window.localStorage.getItem(PROFILE_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<UserProfile> | null;
    return parsed && typeof parsed.id === "string" && typeof parsed.role === "string"
      ? (parsed as UserProfile)
      : null;
  } catch {
    return null;
  }
}

function storeProfile(profile: UserProfile | null): void {
  if (profile) {
    window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
  } else {
    window.localStorage.removeItem(PROFILE_STORAGE_KEY);
  }
}

interface AuthContextValue {
  user: UserProfile | null;
  token: string | null;
  isInitializing: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    window.localStorage.getItem(TOKEN_STORAGE_KEY),
  );
  /*
   * The cached profile lets the shell paint immediately on a reload instead of
   * waiting for GET /auth/me. The server still authorises every request, and
   * the call below refreshes (or clears) the cache in the background.
   */
  const [user, setUser] = useState<UserProfile | null>(() =>
    window.localStorage.getItem(TOKEN_STORAGE_KEY) ? readStoredProfile() : null,
  );
  const [isInitializing, setIsInitializing] = useState(
    () => !window.localStorage.getItem(TOKEN_STORAGE_KEY) || readStoredProfile() === null,
  );
  const queryClient = useQueryClient();

  const clearSession = useCallback(() => {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    storeProfile(null);
    setToken(null);
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    const handleUnauthorized = () => {
      clearSession();
    };
    window.addEventListener("aicte:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("aicte:unauthorized", handleUnauthorized);
  }, [clearSession]);

  useEffect(() => {
    const storedToken = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!storedToken) {
      setIsInitializing(false);
      return;
    }

    let cancelled = false;
    getMe(storedToken)
      .then((profile) => {
        if (!cancelled) {
          setToken(storedToken);
          setUser(profile);
          storeProfile(profile);
        }
      })
      .catch(() => {
        if (!cancelled) {
          clearSession();
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsInitializing(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [clearSession]);

  const login = useCallback(
    async (email: string, password: string) => {
      const result = await loginRequest(email, password);
      queryClient.clear();
      window.localStorage.setItem(TOKEN_STORAGE_KEY, result.access_token);
      storeProfile(result.user);
      setToken(result.access_token);
      setUser(result.user);
    },
    [queryClient],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isInitializing,
      login,
      logout: clearSession,
    }),
    [clearSession, isInitializing, login, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
