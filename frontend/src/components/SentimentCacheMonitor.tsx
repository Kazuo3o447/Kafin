"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Trash2, Database, TrendingUp, AlertTriangle, CheckCircle } from "lucide-react";

interface SentimentStats {
  total_records: number;
  table_size: string;
  avg_record_size_kb: number;
  oldest_record: string | null;
  newest_record: string | null;
  material_events_count: number;
}

interface HealthData {
  status: "healthy" | "warning" | "critical";
  stats: SentimentStats;
  recommendations: string[];
  actions: string[];
}

export default function SentimentCacheMonitor() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [cleaning, setCleaning] = useState(false);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000); // Alle 30s aktualisieren
    return () => clearInterval(interval);
  }, []);

  const fetchHealth = async () => {
    try {
      const response = await fetch("/api/sentiment/health");
      const data = await response.json();
      setHealth(data);
    } catch (error) {
      console.error("Fehler beim Laden der Sentiment-Stats:", error);
    } finally {
      setLoading(false);
    }
  };

  const runCleanup = async (daysToKeep: number = 30) => {
    setCleaning(true);
    try {
      const response = await fetch("/api/sentiment/cleanup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days_to_keep: daysToKeep }),
      });
      
      if (response.ok) {
        await fetchHealth(); // Stats aktualisieren
      }
    } catch (error) {
      console.error("Fehler beim Cleanup:", error);
    } finally {
      setCleaning(false);
    }
  };

  const optimizeStorage = async () => {
    setCleaning(true);
    try {
      await fetch("/api/sentiment/optimize", { method: "POST" });
      await fetchHealth();
    } catch (error) {
      console.error("Fehler bei Optimierung:", error);
    } finally {
      setCleaning(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "healthy": return "bg-green-500";
      case "warning": return "bg-yellow-500";
      case "critical": return "bg-red-500";
      default: return "bg-gray-500";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "healthy": return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "warning": return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case "critical": return <AlertTriangle className="h-4 w-4 text-red-500" />;
      default: return <Database className="h-4 w-4 text-gray-500" />;
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="animate-pulse">Lade Sentiment-Cache Status...</div>
        </CardContent>
      </Card>
    );
  }

  if (!health) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-red-500">Fehler beim Laden der Daten</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Status Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Sentiment-Cache Status
            <Badge className={getStatusColor(health.status)}>
              {health.status.toUpperCase()}
            </Badge>
          </CardTitle>
          <CardDescription>
            Speicherplatz-Statistiken und Health-Check für FinBERT Cache
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold">{health.stats.total_records.toLocaleString()}</div>
              <div className="text-sm text-gray-500">Einträge</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{health.stats.table_size}</div>
              <div className="text-sm text-gray-500">Speicherplatz</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{health.stats.material_events_count}</div>
              <div className="text-sm text-gray-500">Material Events</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">
                {health.stats.avg_record_size_kb || 0}KB
              </div>
              <div className="text-sm text-gray-500">Ø Größe</div>
            </div>
          </div>

          {/* Zeitraum */}
          {(health.stats.oldest_record || health.stats.newest_record) && (
            <div className="mt-4 pt-4 border-t">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-medium">Ältester Eintrag:</span>
                  <div className="text-gray-500">
                    {health.stats.oldest_record 
                      ? new Date(health.stats.oldest_record).toLocaleDateString()
                      : "Keine Daten"
                    }
                  </div>
                </div>
                <div>
                  <span className="font-medium">Neuester Eintrag:</span>
                  <div className="text-gray-500">
                    {health.stats.newest_record 
                      ? new Date(health.stats.newest_record).toLocaleDateString()
                      : "Keine Daten"
                    }
                  </div>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Empfehlungen */}
      {health.recommendations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {getStatusIcon(health.status)}
              Empfehlungen
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {health.recommendations.map((rec, index) => (
                <Alert key={index}>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{rec}</AlertDescription>
                </Alert>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Aktionen */}
      <Card>
        <CardHeader>
          <CardTitle>Cache-Management</CardTitle>
          <CardDescription>
            Manuelle Aktionen zur Speicheroptimierung
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button
              onClick={() => runCleanup(30)}
              disabled={cleaning}
              variant="outline"
              className="flex items-center gap-2"
            >
              <Trash2 className="h-4 w-4" />
              {cleaning ? "Läuft..." : "Cleanup (30 Tage)"}
            </Button>
            
            <Button
              onClick={() => runCleanup(7)}
              disabled={cleaning}
              variant="outline"
              className="flex items-center gap-2"
            >
              <Trash2 className="h-4 w-4" />
              {cleaning ? "Läuft..." : "Cleanup (7 Tage)"}
            </Button>
            
            <Button
              onClick={optimizeStorage}
              disabled={cleaning}
              variant="outline"
              className="flex items-center gap-2"
            >
              <TrendingUp className="h-4 w-4" />
              {cleaning ? "Läuft..." : "Optimieren"}
            </Button>
          </div>
          
          <div className="mt-4 text-sm text-gray-500">
            <div>• Automatischer Cleanup: Täglich um 2:00 Uhr (30 Tage Retention)</div>
            <div>• Manueller Cleanup: Sofortige Löschung alter Daten</div>
            <div>• Optimierung: VACUUM + Index-Neuaufbau</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
