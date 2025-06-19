"use client";

import { useState, useEffect, useCallback } from "react";
import { getUserProfile } from "@/lib/supabase-service";
import { User } from "@/types";

export function useUserProfile() {
    const [profile, setProfile] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<Error | null>(null);

    const fetchProfile = useCallback(async () => {
        try {
            setIsLoading(true);
            const data = await getUserProfile();
            setProfile(data);
            setError(null);
        } catch (err) {
            setError(err as Error);
            console.error("Failed to fetch user profile:", err);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchProfile();
    }, [fetchProfile]);

    const refreshProfile = useCallback(async () => {
        await fetchProfile();
    }, [fetchProfile]);

    return {
        profile,
        isLoading,
        error,
        refreshProfile,
    };
}