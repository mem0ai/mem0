"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Loader2, Calendar, Search, Clock, BarChart3 } from "lucide-react";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { useAuth } from "@/contexts/AuthContext";

interface SimpleLifeTimelineProps {
  onMemorySelect: (memoryId: string | null) => void;
}

interface EventDateRange {
  earliest: Date;
  latest: Date;
  total_memories: number;
  analysis_method: string;
}

export default function SimpleLifeTimeline({ onMemorySelect }: SimpleLifeTimelineProps) {
  const userId = useSelector((state: RootState) => state.profile.userId);
  const { accessToken } = useAuth();
  
  const [allMemories, setAllMemories] = useState<any[]>([]);
  const [eventDateRange, setEventDateRange] = useState<EventDateRange | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzingDateRange, setIsAnalyzingDateRange] = useState(false);
  
  // Custom date range selection
  const [customStartDate, setCustomStartDate] = useState<Date | null>(null);
  const [customEndDate, setCustomEndDate] = useState<Date | null>(null);
  const [customRangeAnalysis, setCustomRangeAnalysis] = useState<string | null>(null);
  const [isAnalyzingCustomRange, setIsAnalyzingCustomRange] = useState(false);

  // Helper: Extract event dates from memory content (not creation dates)
  const extractEventDatesFromContent = (content: string): Date[] => {
    const dates: Date[] = [];
    const text = content.toLowerCase();
    
    // Patterns for years (2019, 2020, etc.)
    const yearMatches = content.match(/\b(19|20)\d{2}\b/g);
    if (yearMatches) {
      yearMatches.forEach(year => {
        const yearNum = parseInt(year);
        if (yearNum >= 1990 && yearNum <= 2030) { // Reasonable range
          dates.push(new Date(yearNum, 0, 1)); // January 1st of that year
        }
      });
    }
    
    // Patterns for "in [month] [year]" or "[month] [year]"
    const monthYearRegex = /\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(19|20)\d{2}\b/gi;
    const monthYearMatches = content.match(monthYearRegex);
    if (monthYearMatches) {
      monthYearMatches.forEach(match => {
        const parsed = new Date(match);
        if (!isNaN(parsed.getTime())) {
          dates.push(parsed);
        }
      });
    }
    
    // Pattern for "last [time period]" - assume recent
    if (text.includes('last weekend') || text.includes('last week') || text.includes('last month')) {
      dates.push(new Date()); // Current date as approximation
    }
    
    // Pattern for "during high school" - approximate to 2019 based on your context
    if (text.includes('high school') || text.includes('varsity team')) {
      dates.push(new Date(2019, 8, 1)); // September 2019
    }
    
    return dates;
  };

  // Helper: Analyze all memories to find actual event date range using existing endpoints
  const analyzeEventDateRange = async (memories: any[]): Promise<EventDateRange | null> => {
    setIsAnalyzingDateRange(true);
    
    try {
      // Step 1: Extract dates from memory content
      const allEventDates: Date[] = [];
      
      memories.forEach(memory => {
        const content = memory.content || '';
        const eventDates = extractEventDatesFromContent(content);
        allEventDates.push(...eventDates);
      });
      
      // Step 2: Use existing deep-life-query endpoint for comprehensive analysis
      const deepQuery = "Please find the earliest date and latest date at which I referenced a date (not based on creation but based on reference of when I said an event or memory took place). Look for specific years, months, dates mentioned in my memories about when events actually happened.";
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765"}/api/v1/memories/deep-life-query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({ query: deepQuery })
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log("Deep life query analysis:", data.response);
        
        // Parse response for additional date insights
        const analysisText = data.response || '';
        const analysisEventDates = extractEventDatesFromContent(analysisText);
        allEventDates.push(...analysisEventDates);
      }
      
      // Step 3: Combine and filter valid dates
      const validEventDates = allEventDates.filter(date => 
        !isNaN(date.getTime()) && 
        date.getFullYear() >= 1990 && 
        date.getFullYear() <= 2030
      );
      
      if (validEventDates.length === 0) {
        // Fallback to creation dates if no event dates found
        const creationDates: Date[] = [];
        memories.forEach(memory => {
          const createdAt = memory.created_at;
          if (typeof createdAt === 'number') {
            const timestamp = createdAt < 10000000000 ? createdAt * 1000 : createdAt;
            creationDates.push(new Date(timestamp));
          } else if (typeof createdAt === 'string') {
            creationDates.push(new Date(createdAt));
          }
        });
        
        if (creationDates.length > 0) {
          return {
            earliest: new Date(Math.min(...creationDates.map(d => d.getTime()))),
            latest: new Date(Math.max(...creationDates.map(d => d.getTime()))),
            total_memories: memories.length,
            analysis_method: "creation_dates_fallback"
          };
        }
        return null;
      }
      
      return {
        earliest: new Date(Math.min(...validEventDates.map(d => d.getTime()))),
        latest: new Date(Math.max(...validEventDates.map(d => d.getTime()))),
        total_memories: memories.length,
        analysis_method: "event_content_analysis + deep_life_query"
      };
      
    } catch (error) {
      console.error("Failed to analyze event date range:", error);
      return null;
    } finally {
      setIsAnalyzingDateRange(false);
    }
  };

  // Fetch all memories and analyze event dates using existing endpoints
  const fetchMemoriesAndAnalyzeEventDates = async () => {
    if (!accessToken) return;
    
    setIsLoading(true);
    
    try {
      // Use existing memories endpoint to get all memories
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765"}/api/v1/memories/?size=200`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });

      if (!response.ok) {
        throw new Error(`Memories fetch failed: ${response.status}`);
      }

      const data = await response.json();
      const memories = data.items || [];
      
      setAllMemories(memories);
      
      // Analyze event date range using memory content + deep-life-query
      const eventRange = await analyzeEventDateRange(memories);
      
      if (eventRange) {
        setEventDateRange(eventRange);
        
        // Initialize custom date range to a meaningful default (last 2 years)
        const defaultEndDate = eventRange.latest;
        const defaultStartDate = new Date(defaultEndDate.getFullYear() - 2, defaultEndDate.getMonth(), defaultEndDate.getDate());
        
        const finalStartDate = defaultStartDate > eventRange.earliest ? defaultStartDate : eventRange.earliest;
        const finalEndDate = defaultEndDate;
        
        console.log('Initializing dates:', {
          earliest: eventRange.earliest,
          latest: eventRange.latest,
          finalStartDate,
          finalEndDate
        });
        
        setCustomStartDate(finalStartDate);
        setCustomEndDate(finalEndDate);
      }
    } catch (error) {
      console.error("Failed to fetch memories and analyze event dates:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // Analyze custom date range using deep-life-query
  const analyzeCustomDateRange = async () => {
    console.log('analyzeCustomDateRange called with:', {
      accessToken: !!accessToken,
      customStartDate,
      customEndDate
    });
    
    if (!accessToken || !customStartDate || !customEndDate) {
      console.log('Missing requirements for analysis:', {
        accessToken: !!accessToken,
        customStartDate: !!customStartDate,
        customEndDate: !!customEndDate
      });
      return;
    }

    setIsAnalyzingCustomRange(true);
    
    try {
      // Format dates for the query
      const startMonth = customStartDate.toLocaleDateString('en-US', { month: 'long' });
      const startYear = customStartDate.getFullYear();
      const endMonth = customEndDate.toLocaleDateString('en-US', { month: 'long' });
      const endYear = customEndDate.getFullYear();
      
      // Create the query in the exact format you showed
      const query = `What happened between the date range ${startMonth} ${startYear} to ${endMonth} ${endYear}`;
      
      console.log("Running custom date range analysis with query:", query);

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765"}/api/v1/memories/deep-life-query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({ query })
      });

      if (!response.ok) {
        throw new Error(`Custom range analysis failed: ${response.status}`);
      }

      const data = await response.json();
      const analysis = data.response || `No analysis available for the period ${startMonth} ${startYear} to ${endMonth} ${endYear}`;

      setCustomRangeAnalysis(analysis);

    } catch (error) {
      console.error("Failed to analyze custom date range:", error);
      setCustomRangeAnalysis("Failed to analyze this date range. Please try again.");
    } finally {
      setIsAnalyzingCustomRange(false);
    }
  };

  // Handle custom date range sliders
  const handleCustomStartDateChange = (value: number[]) => {
    if (!eventDateRange) return;
    
    const totalDays = Math.floor((eventDateRange.latest.getTime() - eventDateRange.earliest.getTime()) / (1000 * 60 * 60 * 24));
    const startDayOffset = Math.floor((value[0] / 100) * totalDays);
    const newStartDate = new Date(eventDateRange.earliest.getTime() + startDayOffset * 24 * 60 * 60 * 1000);
    
    setCustomStartDate(newStartDate);
    
    // Ensure end date is after start date
    if (customEndDate && newStartDate > customEndDate) {
      setCustomEndDate(newStartDate);
    }
  };

  const handleCustomEndDateChange = (value: number[]) => {
    if (!eventDateRange) return;
    
    const totalDays = Math.floor((eventDateRange.latest.getTime() - eventDateRange.earliest.getTime()) / (1000 * 60 * 60 * 24));
    const endDayOffset = Math.floor((value[0] / 100) * totalDays);
    const newEndDate = new Date(eventDateRange.earliest.getTime() + endDayOffset * 24 * 60 * 60 * 1000);
    
    setCustomEndDate(newEndDate);
    
    // Ensure start date is before end date
    if (customStartDate && newEndDate < customStartDate) {
      setCustomStartDate(newEndDate);
    }
  };

  // Quick date range presets
  const setQuickRange = (months: number) => {
    if (!eventDateRange) return;
    
    const endDate = eventDateRange.latest;
    const startDate = new Date(endDate.getFullYear(), endDate.getMonth() - months, endDate.getDate());
    
    setCustomStartDate(startDate > eventDateRange.earliest ? startDate : eventDateRange.earliest);
    setCustomEndDate(endDate);
  };

  // Force scrollable page
  useEffect(() => {
    // Ensure document is scrollable
    document.body.style.overflow = 'auto';
    document.body.style.height = 'auto';
    document.body.style.minHeight = '100vh';
    document.documentElement.style.overflow = 'auto';
    document.documentElement.style.height = 'auto';
    
    // Cleanup function to restore defaults
    return () => {
      document.body.style.overflow = '';
      document.body.style.height = '';
      document.body.style.minHeight = '';
      document.documentElement.style.overflow = '';
      document.documentElement.style.height = '';
    };
  }, []);

  // Initialize timeline on mount
  useEffect(() => {
    if (accessToken && userId) {
      fetchMemoriesAndAnalyzeEventDates();
    }
  }, [accessToken, userId]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">
            {isAnalyzingDateRange ? "Analyzing actual event dates..." : "Loading your life timeline..."}
          </p>
        </div>
      </div>
    );
  }

  if (!eventDateRange || eventDateRange.total_memories === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card className="p-8 text-center max-w-md">
          <h3 className="text-xl font-semibold mb-2">Your Life Timeline Awaits</h3>
          <p className="text-muted-foreground mb-4">
            Add some memories to see your life timeline analysis here.
          </p>
          <Button onClick={fetchMemoriesAndAnalyzeEventDates}>
            <Search className="w-4 h-4 mr-2" />
            Analyze Timeline
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div 
      className="bg-gradient-to-br from-background via-background to-muted/20 p-6"
      style={{ 
        pointerEvents: 'auto',
        minHeight: '100vh',
        width: '100%',
        overflow: 'visible',
        position: 'relative'
      }}
    >
      <div 
        className="max-w-4xl mx-auto space-y-6"
        style={{ 
          pointerEvents: 'auto',
          paddingBottom: '4rem',
          width: '100%',
          minHeight: 'auto'
        }}
      >

        
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold text-foreground">Life Timeline Analysis</h1>
          <p className="text-muted-foreground">
            Explore and analyze any period of your life with AI-powered insights
          </p>
          <div className="flex items-center justify-center gap-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-1">
              <BarChart3 className="w-4 h-4" />
              <span>{eventDateRange.total_memories} memories</span>
            </div>
            <div className="flex items-center gap-1">
              <Calendar className="w-4 h-4" />
              <span>{eventDateRange.earliest.toLocaleDateString()} - {eventDateRange.latest.toLocaleDateString()}</span>
            </div>
            <div className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              <span>{eventDateRange.analysis_method}</span>
            </div>
          </div>
        </div>

        {/* Date Range Selection */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="w-5 h-5" />
              Select Time Period to Analyze
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            
            {/* Quick Presets */}
            <div style={{ position: 'relative', zIndex: 10 }}>
              <label className="text-sm font-medium mb-3 block">Quick Presets</label>
              <div className="flex gap-2 flex-wrap">
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setQuickRange(6)}
                  style={{ position: 'relative', zIndex: 10, pointerEvents: 'auto' }}
                >
                  Last 6 Months
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setQuickRange(12)}
                  style={{ position: 'relative', zIndex: 10, pointerEvents: 'auto' }}
                >
                  Last Year
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setQuickRange(24)}
                  style={{ position: 'relative', zIndex: 10, pointerEvents: 'auto' }}
                >
                  Last 2 Years
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => {
                    setCustomStartDate(eventDateRange.earliest);
                    setCustomEndDate(eventDateRange.latest);
                  }}
                  style={{ position: 'relative', zIndex: 10, pointerEvents: 'auto' }}
                >
                  Full Timeline
                </Button>
              </div>
            </div>

            {/* Custom Date Range */}
            <div className="grid md:grid-cols-2 gap-6">
              
              {/* Start Date */}
              <div>
                <label className="text-sm font-medium mb-3 block">Start Date</label>
                <div className="mb-3 p-3 bg-muted/50 rounded-md text-center">
                  <div className="text-lg font-semibold">
                    {customStartDate?.toLocaleDateString('en-US', { 
                      month: 'long', 
                      year: 'numeric' 
                    })}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {customStartDate?.toLocaleDateString()}
                  </div>
                </div>
                <Slider
                  value={[customStartDate && eventDateRange ? 
                    ((customStartDate.getTime() - eventDateRange.earliest.getTime()) / 
                    (eventDateRange.latest.getTime() - eventDateRange.earliest.getTime())) * 100 : 0]}
                  onValueChange={handleCustomStartDateChange}
                  max={100}
                  min={0}
                  step={1}
                  className="w-full"
                />
              </div>

              {/* End Date */}
              <div>
                <label className="text-sm font-medium mb-3 block">End Date</label>
                <div className="mb-3 p-3 bg-muted/50 rounded-md text-center">
                  <div className="text-lg font-semibold">
                    {customEndDate?.toLocaleDateString('en-US', { 
                      month: 'long', 
                      year: 'numeric' 
                    })}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {customEndDate?.toLocaleDateString()}
                  </div>
                </div>
                <Slider
                  value={[customEndDate && eventDateRange ? 
                    ((customEndDate.getTime() - eventDateRange.earliest.getTime()) / 
                    (eventDateRange.latest.getTime() - eventDateRange.earliest.getTime())) * 100 : 100]}
                  onValueChange={handleCustomEndDateChange}
                  max={100}
                  min={0}
                  step={1}
                  className="w-full"
                />
              </div>
            </div>

            {/* Analysis Button */}
            <div className="text-center" style={{ position: 'relative', zIndex: 10 }}>
              <Button 
                onClick={() => {
                  console.log('Button clicked!');
                  analyzeCustomDateRange();
                }}
                disabled={isAnalyzingCustomRange || !customStartDate || !customEndDate}
                size="lg"
                className="px-8"
                style={{ 
                  position: 'relative', 
                  zIndex: 10, 
                  pointerEvents: 'auto'
                }}
              >
                {isAnalyzingCustomRange ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    Analyzing Period...
                  </>
                ) : (
                  <>
                    <Search className="w-5 h-5 mr-2" />
                    Analyze This Period
                  </>
                )}
              </Button>
              
              {/* Debug info - can be removed later */}
              {(!customStartDate || !customEndDate) && (
                <p className="text-xs text-red-500 mt-2">
                  Debug: Missing dates - Start: {customStartDate?.toString() || 'null'}, End: {customEndDate?.toString() || 'null'}
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Analysis Results */}
        {customRangeAnalysis && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5" />
                  Analysis Results
                  <span className="text-sm text-muted-foreground font-normal">
                    ({customStartDate?.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })} - {customEndDate?.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })})
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="prose prose-sm max-w-none">
                  <div className="whitespace-pre-wrap text-foreground leading-relaxed">
                    {customRangeAnalysis}
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Related Memories Preview */}
        {customRangeAnalysis && allMemories.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="w-5 h-5" />
                Related Memories from This Period
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {allMemories
                  .filter(memory => {
                    // Filter memories that fall within the selected date range
                    const content = memory.content || '';
                    const createdAt = memory.created_at;
                    
                    // Check creation date
                    if (typeof createdAt === 'number') {
                      const timestamp = createdAt < 10000000000 ? createdAt * 1000 : createdAt;
                      const creationDate = new Date(timestamp);
                      return creationDate >= customStartDate && creationDate <= customEndDate;
                    }
                    
                    // Check content for year mentions
                    if (customStartDate && customEndDate) {
                      const startYear = customStartDate.getFullYear();
                      const endYear = customEndDate.getFullYear();
                      
                      for (let year = startYear; year <= endYear; year++) {
                        if (content.includes(year.toString())) {
                          return true;
                        }
                      }
                    }
                    
                    return false;
                  })
                  .slice(0, 6)
                  .map((memory) => {
                    const createdAt = memory.created_at;
                    let displayDate = 'Unknown date';
                    if (typeof createdAt === 'number') {
                      const timestamp = createdAt < 10000000000 ? createdAt * 1000 : createdAt;
                      displayDate = new Date(timestamp).toLocaleDateString();
                    } else if (typeof createdAt === 'string') {
                      displayDate = new Date(createdAt).toLocaleDateString();
                    }
                    
                    return (
                      <Card 
                        key={memory.id}
                        className="cursor-pointer hover:shadow-md transition-shadow"
                        onClick={() => onMemorySelect(memory.id)}
                      >
                        <CardContent className="p-4">
                          <p className="text-sm line-clamp-3 mb-3">{memory.content}</p>
                          <div className="flex justify-between items-center text-xs text-muted-foreground">
                            <span>{memory.app_name}</span>
                            <span>{displayDate}</span>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
} 