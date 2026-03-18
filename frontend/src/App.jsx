import { useState, useEffect, useRef, useMemo } from 'react'
import { format, addDays } from 'date-fns'
import { MapPin, Clock, Heart, Bookmark, Calendar, ChevronRight, ChevronDown, Activity, BookOpen, Ticket, X, CheckCircle, CreditCard, ArrowUp, ArrowDown, User, ExternalLink, ArrowUpRight, Moon, Sun, Briefcase, Plane, Zap, Flame, Lock, Flag, PlusSquare, Share, Download, Smartphone } from 'lucide-react'
import { auth, db, googleProvider, appleProvider } from './firebase'
import { signInWithPopup, signInWithEmailAndPassword, createUserWithEmailAndPassword, onAuthStateChanged, signOut, updateProfile } from 'firebase/auth'
import { doc, getDoc, setDoc, updateDoc, arrayUnion, arrayRemove } from 'firebase/firestore'
import { supabase } from './lib/supabase'
import ReactGA from "react-ga4"
import { useInView } from 'react-intersection-observer'
import './App.css'

function App() {
  console.log("App function started executing");
  const [events, setEvents] = useState([])
  const [areasDict, setAreasDict] = useState({})

  // State
  const getLogicalToday = () => {
    return new Date() // Return actual calendar today
  }
  const [selectedDate, setSelectedDate] = useState(getLogicalToday())
  const [selectedPrefecture, setSelectedPrefecture] = useState('東京')
  const [selectedArea, setSelectedArea] = useState('All')
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [isBookmarksModalOpen, setIsBookmarksModalOpen] = useState(false)
  const [isPurchaseModalOpen, setIsPurchaseModalOpen] = useState(false)
  const [isPassModalOpen, setIsPassModalOpen] = useState(false)
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false)
  const [isAboutModalOpen, setIsAboutModalOpen] = useState(false)
  const [isInstallModalOpen, setIsInstallModalOpen] = useState(false)
  const [showOnlyLiked, setShowOnlyLiked] = useState(false)
  const [showOnlyFree, setShowOnlyFree] = useState(false)
  const [authMode, setAuthMode] = useState('login') // 'login' or 'signup'
  const [displayName, setDisplayName] = useState('')
  const [path, setPath] = useState(window.location.pathname) // Manual routing

  // Auth State
  const [currentUser, setCurrentUser] = useState(null)
  const [authError, setAuthError] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  // LocalStorage state for PASS
  const [userPassType, setUserPassType] = useState(() => {
    try {
      return localStorage.getItem('userPassType') || null
    } catch {
      return null
    }
  })

  // Admin Detection
  const isAdmin = useMemo(() => {
    // return true; // TEMPORARY: Force true for local testing
    return currentUser && currentUser.uid === import.meta.env.VITE_ADMIN_UID;
  }, [currentUser]);

  const [passCurrentTime, setPassCurrentTime] = useState(new Date())

  // LocalStorage state
  const [likedVenues, setLikedVenues] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('likedVenues') || '[]')
    } catch {
      return []
    }
  })

  const [reportedVideos, setReportedVideos] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('reportedVideos') || '[]')
    } catch {
      return []
    }
  })

  const [bookmarkedEvents, setBookmarkedEvents] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('bookmarkedEvents') || '[]')
    } catch {
      return []
    }
  })

  const [isLoading, setIsLoading] = useState(true)
  const [videoModal, setVideoModal] = useState(null) // { artistName, loading, videoId, reported, eventId, ticketUrl, isConfirming }

  // PWA Install states
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [isInstallable, setIsInstallable] = useState(false);
  const [showInstallBanner, setShowInstallBanner] = useState(() => {
    try {
      return localStorage.getItem('installBannerDismissed') !== 'true';
    } catch {
      return true;
    }
  });

  // Platform detection
  const isIOS = useMemo(() => {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  }, []);

  const isSafari = useMemo(() => {
    return /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
  }, []);

  const isMobile = useMemo(() => {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  }, []);

  const isStandalone = useMemo(() => {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;
  }, []);


  // Save to localStorage
  useEffect(() => {
    localStorage.setItem('likedVenues', JSON.stringify(likedVenues))
  }, [likedVenues])

  useEffect(() => {
    localStorage.setItem('reportedVideos', JSON.stringify(reportedVideos))
  }, [reportedVideos])

  useEffect(() => {
    localStorage.setItem('bookmarkedEvents', JSON.stringify(bookmarkedEvents))
  }, [bookmarkedEvents])

  useEffect(() => {
    if (userPassType) {
      localStorage.setItem('userPassType', userPassType)
    } else {
      localStorage.removeItem('userPassType')
    }
  }, [userPassType])

  // Moving clock for Door Ticket Pass
  useEffect(() => {
    let timer
    if (isPassModalOpen) {
      timer = setInterval(() => setPassCurrentTime(new Date()), 1000)
    }
    // No else block setting date here to avoid loops
    return () => {
      if (timer) clearInterval(timer)
    }
  }, [isPassModalOpen])

  // Fetch Areas (Static Dictionary)
  useEffect(() => {
    const handlePopState = () => {
      setPath(window.location.pathname)
    }
    window.addEventListener('popstate', handlePopState)

    // Parse URL on mount
    const params = new URLSearchParams(window.location.search);
    const urlPref = params.get('pref');
    if (urlPref) setSelectedPrefecture(urlPref);
    
    const urlArea = params.get('area');
    if (urlArea) setSelectedArea(urlArea);
    
    const urlDate = params.get('date');
    if (urlDate) {
      const parsedDate = new Date(urlDate);
      if (!isNaN(parsedDate.getTime())) {
        setSelectedDate(parsedDate);
      }
    }
    
    const urlFree = params.get('free');
    if (urlFree === 'true') setShowOnlyFree(true);

    // PWA Install prompt listener
    const handleBeforeInstallPrompt = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setIsInstallable(true);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);

    // Hardcoded areas dict to replace the backend API
    setAreasDict({
      "東京": ["渋谷", "新宿", "下北沢"]
    })

    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    };
  }, [])

  // Update URL params when filters change
  useEffect(() => {
    const params = new URLSearchParams();
    if (selectedPrefecture !== '東京') params.set('pref', selectedPrefecture);
    if (selectedArea !== 'All') params.set('area', selectedArea);
    
    const dateStr = format(selectedDate, 'yyyy-MM-dd');
    const todayStr = format(new Date(), 'yyyy-MM-dd'); // Use calendar today for URL comparison
    if (dateStr !== todayStr) params.set('date', dateStr);
    
    if (showOnlyFree) params.set('free', 'true');
    
    const newSearch = params.toString();
    const currentSearch = window.location.search.replace(/^\?/, '');
    
    if (newSearch !== currentSearch) {
      const newUrl = window.location.pathname + (newSearch ? `?${newSearch}` : '');
      window.history.replaceState(null, '', newUrl);
    }
  }, [selectedPrefecture, selectedArea, selectedDate, showOnlyFree]);

  // --- UTM Tracker Utility ---

  // Geolocation for initial area setting
  useEffect(() => {
    // Check for guide parameter to auto-open About modal
    const params = new URLSearchParams(window.location.search)
    if (params.get('guide') === 'true') {
      setIsAboutModalOpen(true)
    }

    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const lat = position.coords.latitude
          const lon = position.coords.longitude
          const hubs = [
            { name: "渋谷", lat: 35.6580, lon: 139.7016 },
            { name: "新宿", lat: 35.6896, lon: 139.7005 },
            { name: "下北沢", lat: 35.6616, lon: 139.6670 }
          ]
          
          let minDistance = Infinity
          let nearestArea = null
          
          hubs.forEach(hub => {
            const R = 6371 // Radius of the earth in km
            const dLat = (hub.lat - lat) * Math.PI / 180
            const dLon = (hub.lon - lon) * Math.PI / 180
            const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat * Math.PI / 180) * Math.cos(hub.lat * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2)
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a))
            const distance = R * c
            
            if (distance < minDistance) {
              minDistance = distance
              nearestArea = hub.name
            }
          })
          
          // If within 10km of a hub, auto-select it. Otherwise just select Tokyo All
          if (minDistance < 10 && nearestArea) {
            setSelectedPrefecture("東京")
            setSelectedArea(nearestArea)
          } else {
            setSelectedPrefecture("東京")
            setSelectedArea("All")
          }
        },
        (err) => console.log("Geolocation error/denied (expected behavior):", err.message),
        { timeout: 5000, enableHighAccuracy: false }
      )
    }
  }, [])

  // SEO: Dynamic Title, Meta Description and JSON-LD
  useEffect(() => {
    const areaPath = selectedArea === 'All' ? selectedPrefecture : selectedArea;
    const dateStr = format(selectedDate, 'M月d日');
    const newTitle = `${areaPath}の${dateStr}のライブ情報 - ドアチケ`;
    document.title = newTitle;

    // Update meta description dynamically for more relevance
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) {
      metaDesc.setAttribute('content', `${areaPath}の${dateStr}のライブ情報・当日券情報を網羅。出演アーティストの動画をチェックして、今すぐライブハウスへ。`);
    }

    // JSON-LD for Events (Google Event Search)
    const scriptId = 'json-ld-events';
    let script = document.getElementById(scriptId);
    if (!script) {
      script = document.createElement('script');
      script.id = scriptId;
      script.type = 'application/ld+json';
      document.head.appendChild(script);
    }

    // Only include published events for JSON-LD
    const publishedEvents = (events || []).filter(e => e.status === 'published' || !e.status).slice(0, 20); // Limit to 20 for performance
    const jsonLdData = publishedEvents.map(evt => {
      if (!evt || !evt.event_date || !evt.livehouse) return null;
      try {
        const dateObj = new Date(evt.event_date);
        if (isNaN(dateObj.getTime())) return null;

        return {
          "@context": "https://schema.org",
          "@type": "Event",
          "name": evt.title || "Unknown Event",
          "startDate": `${format(dateObj, 'yyyy-MM-dd')}T${evt.open_time || '19:00'}`,
          "location": {
            "@type": "Place",
            "name": evt.livehouse.name,
            "address": {
              "@type": "PostalAddress",
              "addressLocality": evt.livehouse.area || "",
              "addressRegion": evt.livehouse.prefecture || "",
              "addressCountry": "JP"
            }
          },
          "image": evt.image_url || "https://doortike.com/ogp.png",
          "description": `${evt.livehouse.name}で開催されるライブ情報。出演: ${Array.isArray(evt.artists_data) ? evt.artists_data.map(a => a?.name).filter(Boolean).join(', ') : '各アーティスト'}`,
          "offers": {
            "@type": "Offer",
            "url": evt.ticket_url || "https://doortike.com/",
            "price": "0", // Default to 0 as exact price parsing is complex
            "priceCurrency": "JPY",
            "availability": "https://schema.org/InStock"
          }
        };
      } catch (err) {
        return null;
      }
    }).filter(Boolean);

    script.text = JSON.stringify(jsonLdData);
  }, [selectedArea, selectedPrefecture, selectedDate, events]);

  // Listen to Auth State changes and sync with Firestore
  useEffect(() => {
    if (!auth) return;
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      setCurrentUser(user)
      if (user) {
        // Fetch user data from Firestore
        try {
          const userDocRef = doc(db, 'users', user.uid)
          const userDocSnap = await getDoc(userDocRef)

          if (userDocSnap.exists()) {
            const userData = userDocSnap.data()
            if (userData.likedVenues) setLikedVenues(userData.likedVenues)
            if (userData.bookmarkedEvents) setBookmarkedEvents(userData.bookmarkedEvents)
          } else {
            // New user: Sync current LocalStorage to Firestore (Initial Sync)
            await setDoc(userDocRef, {
              likedVenues: likedVenues,
              bookmarkedEvents: bookmarkedEvents,
              email: user.email,
              createdAt: new Date()
            })
          }
        } catch (error) {
          console.error("Error syncing with Firestore:", error)
        }
      } else {
        // Logout: Reset to LocalStorage state
        try {
          const localLiked = JSON.parse(localStorage.getItem('likedVenues') || '[]')
          const localBookmarks = JSON.parse(localStorage.getItem('bookmarkedEvents') || '[]')
          setLikedVenues(localLiked)
          setBookmarkedEvents(localBookmarks)
        } catch (e) {
          console.error("Error resetting local data:", e)
        }
      }
    })
    return () => unsubscribe()
  }, [])

  // Fetch Events from Supabase when date or area changes
  useEffect(() => {
    const fetchEventsFromSupabase = async () => {
      setIsLoading(true)
      try {
        const dateStr = format(selectedDate, 'yyyy-MM-dd')
        const realToday = new Date()
        const isSelectedDateRealToday = format(selectedDate, 'yyyy-MM-dd') === format(realToday, 'yyyy-MM-dd')
        
        let query = supabase
          .from('events')
          .select(`
            *,
            livehouse:livehouses!inner(*)
          `)
          .eq('status', 'published')

        if (isSelectedDateRealToday && realToday.getHours() < 4) {
          // Fetch both today and yesterday
          const yesterdayStr = format(addDays(selectedDate, -1), 'yyyy-MM-dd')
          query = query.in('date', [dateStr, yesterdayStr])
        } else {
          query = query.eq('date', dateStr)
        }

        if (selectedPrefecture !== 'All') {
          query = query.eq('livehouse.prefecture', selectedPrefecture)
        }
        // Area filtering is handled entirely on the client side (filteredEvents useMemo)
        // to prevent loading flickers when switching areas.

        const { data, error } = await query
        
        if (error) {
          console.error("Supabase error fetching events:", error)
          setIsLoading(false)
          return
        }

        let fetchedEvents = data || []

        const formattedEvents = fetchedEvents.map(evt => {
            return {
                ...evt,
                id: evt.id,
                title: evt.title,
                performers: evt.performers,
                date: evt.date,
              open_time: evt.open_time,
              start_time: evt.start_time,
              price_info: evt.price_info,
              ticket_url: evt.ticket_url,
              coupon_url: evt.coupon_url,
              is_pr: evt.is_pr,
              pr_type: evt.pr_type,
              is_pickup: evt.is_pickup,
              pickup_type: evt.pickup_type,
              is_midnight: evt.is_midnight,
              livehouse: evt.livehouse
           }
        })
        
        // Ensure consistent sorting (e.g. by open_time)
        formattedEvents.sort((a, b) => {
          if (a.is_pr && !b.is_pr) return -1;
          if (!a.is_pr && b.is_pr) return 1;
          const timeA = a.open_time || "23:59";
          const timeB = b.open_time || "23:59";
          return timeA.localeCompare(timeB);
        });

        setEvents(formattedEvents)
      } catch (err) {
        console.error("Unknown error catching events:", err)
      } finally {
        setIsLoading(false)
      }
    }

    fetchEventsFromSupabase()
  }, [selectedDate, selectedPrefecture])
  // === References for Modal Scrolling ===
  const modalBodyRef = useRef(null)

  const scrollToModalTop = () => {
    if (modalBodyRef.current) {
      modalBodyRef.current.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const scrollToModalBottom = () => {
    if (modalBodyRef.current) {
      modalBodyRef.current.scrollTo({ top: modalBodyRef.current.scrollHeight, behavior: 'smooth' })
    }
  }

  // Navigation Logic (Manual Router)
  const navigateTo = (newPath) => {
    window.history.pushState({}, '', newPath)
    setPath(newPath)
    window.scrollTo(0, 0)
  }

  const toggleVenueLike = async (venueId) => {
    let newLiked;
    if (likedVenues.includes(venueId)) {
      newLiked = likedVenues.filter(id => id !== venueId);
    } else {
      newLiked = [...likedVenues, venueId];
    }
    setLikedVenues(newLiked);

    if (currentUser) {
      try {
        const userDocRef = doc(db, 'users', currentUser.uid);
        await updateDoc(userDocRef, {
          likedVenues: newLiked
        });
      } catch (error) {
        console.error("Error updating liked venues in Firestore:", error);
      }
    }
  }

  // === Video Reporting ===
  const [isReporting, setIsReporting] = useState(false)
  const handleReportVideo = async (confirmed = false) => {
    if (!videoModal || !videoModal.eventId || isReporting) return;

    if (!confirmed) {
      setVideoModal(prev => ({ ...prev, isConfirming: true }));
      return;
    }

    // Optimistic Update: Hide video immediately for "Magic UX"
    setVideoModal(prev => ({ ...prev, reported: true, isConfirming: false }));
    setIsReporting(true);

    // Persist locally so it can't be replayed on this terminal, even if sync fails
    if (!reportedVideos.includes(videoModal.artistName)) {
      setReportedVideos(prev => [...prev, videoModal.artistName]);
    }

    try {
      const { error } = await supabase
        .rpc('report_video', { 
          p_event_id: videoModal.eventId, 
          p_artist_name: videoModal.artistName 
        })

      if (error) throw error;
    } catch (error) {
      console.error("Error reporting video:", error)
      // Even if network fails, we keep it hidden for UX, but alert the user once
      console.log("Failed to sync report to backend, but UI is updated optimistically.");
    } finally {
      setIsReporting(false);
    }
  }

  const handleToggleStaffPick = async (e, evt) => {
    e.stopPropagation();
    if (!isAdmin) return;

    const newPickupType = evt.pickup_type === 'staff' ? null : 'staff';
    const newIsPickup = !!newPickupType;

    // Optimistic Update
    setEvents(prev => prev.map(item => 
      item.id === evt.id ? { ...item, is_pickup: newIsPickup, pickup_type: newPickupType } : item
    ));

    try {
      const { error } = await supabase
        .from('events')
        .update({ 
          is_pickup: newIsPickup, 
          pickup_type: newPickupType 
        })
        .eq('id', evt.id);

      if (error) throw error;
    } catch (err) {
      console.error("Error toggling staff pick:", err);
      // Rollback
      setEvents(prev => prev.map(item => 
        item.id === evt.id ? { ...item, is_pickup: evt.is_pickup, pickup_type: evt.pickup_type } : item
      ));
    }
  }

  // === Authentication Handlers ===
  const handleGoogleLogin = async () => {
    if (!auth) return setAuthError('Firebaseの設定が完了していません（.env.localを設定してください）');
    try {
      setAuthError('')
      await signInWithPopup(auth, googleProvider)
      setIsAuthModalOpen(false)
    } catch (error) {
      setAuthError('Googleログインに失敗しました')
      console.error(error)
    }
  }

  const handleAppleLogin = async () => {
    if (!auth) return setAuthError('Firebaseの設定が完了していません（.env.localを設定してください）');
    try {
      setAuthError('')
      await signInWithPopup(auth, appleProvider)
      setIsAuthModalOpen(false)
    } catch (error) {
      setAuthError('Appleログインに失敗しました')
      console.error(error)
    }
  }

  const handleEmailLogin = async (e) => {
    e.preventDefault()
    if (!auth) return setAuthError('Firebaseの設定が完了していません（.env.localを設定してください）');
    try {
      setAuthError('')
      await signInWithEmailAndPassword(auth, email, password)
      setIsAuthModalOpen(false)
      // Reset form
      setEmail('')
      setPassword('')
    } catch (error) {
      if (error.code === 'auth/user-not-found' || error.code === 'auth/wrong-password') {
        setAuthError('メールアドレスまたはパスワードが間違っています')
      } else if (error.code === 'auth/invalid-email') {
        setAuthError('無効なメールアドレス形式です')
      } else {
        setAuthError('ログインに失敗しました。時間をおいて再度お試しください')
      }
      console.error(error)
    }
  }

  const handleEmailSignUp = async (e) => {
    e.preventDefault()
    if (!auth) return setAuthError('Firebaseの設定が完了していません');
    try {
      setAuthError('')
      const userCredential = await createUserWithEmailAndPassword(auth, email, password)

      // ユーザー名の設定
      if (displayName) {
        await updateProfile(userCredential.user, {
          displayName: displayName
        })
      }

      setIsAuthModalOpen(false)
      // Reset form
      setEmail('')
      setPassword('')
      setDisplayName('')
    } catch (error) {
      if (error.code === 'auth/email-already-in-use') {
        setAuthError('このメールアドレスは既に登録されています')
      } else if (error.code === 'auth/weak-password') {
        setAuthError('パスワードは6文字以上で設定してください')
      } else {
        setAuthError('登録に失敗しました。入力内容をご確認ください')
      }
      console.error(error)
    }
  }

  const handleSignOut = async () => {
    if (!auth) return;
    await signOut(auth)
    setIsAuthModalOpen(false)
  }

  // ブックマークされたイベントを最新の取得データで随時更新する（スキーマ変更時などのキャッシュ古化対策）
  useEffect(() => {
    if (events.length > 0 && bookmarkedEvents.length > 0) {
      setBookmarkedEvents(prev => {
        let isUpdated = false
        const next = prev.map(b => {
          const fresh = events.find(e => e.id === b.id)
          if (fresh && JSON.stringify(fresh) !== JSON.stringify(b)) {
            isUpdated = true
            return fresh
          }
          return b
        })
        return isUpdated ? next : prev
      })
    }
  }, [events])

  const toggleBookmark = async (event) => {
    const isBookmarked = bookmarkedEvents.some(b => b.id === event.id)
    let newBookmarks;
    if (isBookmarked) {
      // 削除
      newBookmarks = bookmarkedEvents.filter(b => b.id !== event.id);
      setBookmarkedEvents(newBookmarks);
    } else {
      // 追加
      newBookmarks = [...bookmarkedEvents, event];
      setBookmarkedEvents(newBookmarks);
    }

    // Update local events state to reflect the new bookmark count immediately
    setEvents(prev => prev.map(e => {
      if (e.id === event.id) {
        const increment = isBookmarked ? -1 : 1;
        return { ...e, bookmark_count: (e.bookmark_count || 0) + increment };
      }
      return e;
    }));

    if (currentUser) {
      try {
        const userDocRef = doc(db, 'users', currentUser.uid);
        await updateDoc(userDocRef, {
          bookmarkedEvents: newBookmarks
        });
      } catch (error) {
        console.error("Error updating bookmarks in Firestore:", error);
      }
    }

    // Sync Bookmark Count to Supabase (Regardless of guest/auth for aggregate tracking)
    try {
      const increment = isBookmarked ? -1 : 1;
      const { error } = await supabase.rpc('handle_bookmark_count', {
        p_event_id: event.id,
        p_increment: increment
      });
      if (error) throw error;
    } catch (error) {
      console.error("Error syncing bookmark count to Supabase:", error);
    }
  }

  // Handle outside click for dropdown target area
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (isDropdownOpen && !event.target.closest('.custom-dropdown')) {
        setIsDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isDropdownOpen])

  const handleInstallClick = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      console.log('User accepted the install prompt');
    }
    setDeferredPrompt(null);
    setIsInstallable(false);
  };

  const isEventBookmarked = (id) => bookmarkedEvents.some(b => b.id === id)

  // Handle late-night events: if it's before 4 AM, "today" should be the previous calendar day.
  const now = new Date()
  const today = new Date(now)
  // Remove 4 AM shift here as well for consistent reference
  const tomorrow = addDays(today, 1)

  const todayStr = format(today, 'yyyy-MM-dd')

  // Group bookmarked events by date to solve the mix-up issue
  // Also filter out past events (only show today or later)
  const groupedBookmarks = bookmarkedEvents
    .filter(evt => evt.date >= todayStr)
    .reduce((acc, evt) => {
      const dateStr = evt.date || 'Unknown'
      if (!acc[dateStr]) acc[dateStr] = []
      acc[dateStr].push(evt)
      return acc
    }, {})

  const sortedBookmarkDates = Object.keys(groupedBookmarks).sort()

  // Calculate the count of valid (upcoming) bookmarks for the badge
  const upcomingBookmarksCount = bookmarkedEvents.filter(evt => evt.date >= todayStr).length

  // Auto-close bookmark modal when visible list becomes empty
  useEffect(() => {
    if (isBookmarksModalOpen && upcomingBookmarksCount === 0) {
      setIsBookmarksModalOpen(false)
    }
  }, [upcomingBookmarksCount, isBookmarksModalOpen])

  // === Handlers for scroll buttons ===
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const scrollToBottom = () => {
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' })
  }

  // === Filtering Logic ===
  const isFreeEvent = (priceInfo) => {
    if (!priceInfo) return false
    const freeKeywords = ['0円', '¥0', '無料', '0 yen', 'free']
    return freeKeywords.some(keyword => priceInfo.toLowerCase().includes(keyword))
  }

  const filteredEvents = useMemo(() => {
    // Phase 16: Initial filtering (Prefecture + Area + Date, but skip showOnlyLiked for now)
    const initialFiltered = events.filter(e => {
      const matchesArea = selectedArea === 'All' || e.livehouse.area === selectedArea
      const matchesPrefecture = selectedPrefecture === 'All' || e.livehouse.prefecture === selectedPrefecture

      if (!matchesPrefecture) return false
      if (!e.is_pr && !matchesArea) return false

      return true
    })

    // Phase 17: Merge Circuit Events
    const mergedMap = new Map()
    const mergedResult = []

    initialFiltered.forEach(evt => {
      const ticketUrl = evt.ticket_url?.trim()
      if (ticketUrl && ticketUrl !== "") {
        const key = `${evt.date}_${ticketUrl}`
        if (mergedMap.has(key)) {
          const existing = mergedMap.get(key)
          if (!existing.venues) {
            existing.venues = [{ id: existing.livehouse.id, name: existing.livehouse.name }]
          }
          if (!existing.venues.some(v => v.id === evt.livehouse.id)) {
            existing.venues.push({ id: evt.livehouse.id, name: evt.livehouse.name })
            existing.livehouse.name += ` / ${evt.livehouse.name}`
          }
        } else {
          const clone = {
            ...evt,
            livehouse: { ...evt.livehouse },
            venues: [{ id: evt.livehouse.id, name: evt.livehouse.name }]
          }
          mergedMap.set(key, clone)
          mergedResult.push(clone)
        }
      } else {
        mergedResult.push(evt)
      }
    })

    // Phase 17: Post-Merge Favorites Filtering
    // An event is kept if:
    // 1. Favorites filter is OFF
    // 2. OR Favorites filter is ON and (event has a single venue that's favorited OR at least one of its multiple venues is favorited)
    let filteredResult = mergedResult
    if (showOnlyLiked) {
      filteredResult = mergedResult.filter(e => {
        if (e.venues && e.venues.length > 0) {
          return e.venues.some(v => likedVenues.includes(v.id))
        }
        return likedVenues.includes(e.livehouse.id)
      })
    }

    let finalFiltered = filteredResult
    if (showOnlyFree) {
      finalFiltered = filteredResult.filter(e => e.is_pr || isFreeEvent(e.price_info))
    }

    const todayStr = format(selectedDate, 'yyyy-MM-dd')
    const tomorrowStr = format(addDays(selectedDate, 1), 'yyyy-MM-dd')
    const realToday = new Date()
    const isSelectedDateRealToday = todayStr === format(realToday, 'yyyy-MM-dd')
    const isBefore4AM = realToday.getHours() < 4

    // 1. Separate by day
    // If it's today and before 4 AM, include yesterday's midnight events
    let todayEvents = []
    if (isSelectedDateRealToday && isBefore4AM) {
      const yesterdayStr = format(addDays(selectedDate, -1), 'yyyy-MM-dd')
      todayEvents = finalFiltered.filter(e => 
        e.date === todayStr || (e.date === yesterdayStr && e.is_midnight)
      )
    } else {
      todayEvents = finalFiltered.filter(e => e.date === todayStr)
    }
    
    const tomorrowEventsRaw = finalFiltered.filter(e => e.date === tomorrowStr)

    // 2. Today's grouping
    const todayRegularFull = todayEvents.filter(e => !e.is_midnight && e.date === todayStr)
    const todayMidnightFull = todayEvents.filter(e => e.is_midnight)

    const processGroup = (group) => {
      // 1. Group by priority status
      const prs = group.filter(e => e.is_pr)
      const pickups = group.filter(e => !e.is_pr && (e.is_pickup || e.pickup_type === 'staff'))
      const others = group.filter(e => !e.is_pr && !e.is_pickup && e.pickup_type !== 'staff')

      const sortByOpenTime = (a, b) => {
        const timeA = a.open_time || '99:99'
        const timeB = b.open_time || '99:99'
        return timeA.localeCompare(timeB)
      }

      // 2. Sort each priority group by time for inner consistency
      prs.sort(sortByOpenTime)
      pickups.sort(sortByOpenTime)
      others.sort(sortByOpenTime)

      // 3. Concatenate based on rule: PR > STAFF PICK > OTHERS
      // "HOT" and "Happening" (開催中) do not influence position anymore.
      return [...prs, ...pickups, ...others]
    }

    const todayRegular = processGroup(todayRegularFull)
    const todayMidnight = processGroup(todayMidnightFull)
    const tomorrowEvents = processGroup(tomorrowEventsRaw)

    const displayCount = todayEvents.length

    return {
      groups: {
        todayRegular,
        todayMidnight,
        tomorrowEvents
      },
      displayCount
    }
  }, [events, showOnlyLiked, showOnlyFree, likedVenues, selectedArea, selectedPrefecture, selectedDate])

  const { groups, displayCount } = filteredEvents

  // Assuming currentPage and setCurrentPage are defined earlier in the component, e.g.:
  // const [currentPage, setCurrentPage] = useState('home');
  // And isLoading is also defined, e.g.:
  // const [isLoading, setIsLoading] = useState(true);

  if (isLoading) {
    return <div className="loading-screen">Loading...</div>
  }

  // Terms of Service View
  if (path === '/terms') {
    return (
      <div className="terms-page">
        <header className="terms-header">
          <button className="back-btn" onClick={() => navigateTo('/')}>
            <ChevronDown style={{ transform: 'rotate(90deg)' }} size={24} />
            ホームへ戻る
          </button>
          <h1>利用規約</h1>
        </header>

        <main className="terms-content glass-panel">
          <p style={{ marginBottom: '24px', fontSize: '0.95rem', lineHeight: '1.6' }}>
            この利用規約（以下、「本規約」といいます。）は、ドアチケ運営（以下、「当運営」といいます。）が提供するサービス（以下、「本サービス」といいます。）の利用条件を定めるものです。ユーザーの皆様（以下、「ユーザー」といいます。）には、本規約に従って本サービスをご利用いただきます。
          </p>

          <section>
            <h2>第1条（適用）</h2>
            <p>本規約は、ユーザーと当運営との間の本サービスの利用に関わる一切の関係に適用されるものとします。ユーザーが本サービス内で決済を行った時点で、本規約に同意したものとみなします。</p>
          </section>

          <section>
            <h2>第2条（PR枠・応援広告の購入と免責）</h2>
            <p>本サービス内の広告枠（以下、「PR枠」）は、出演者・主催者のほか、ファンの方でも「応援広告」として購入することが可能です。</p>
            <p>ファンの方がPR枠を購入した場合において、公式（出演者、事務所、主催者等）との間で広告掲載に関するトラブル（「無断で広告を出さないでほしい」等のクレーム）が発生した際は、購入者ご自身の責任と負担において解決するものとし、当運営は一切の責任を負いません。</p>
            <p>公式関係者から当運営に対し直接の掲載取り下げ要請があった場合、当運営は事前の通知なく該当のPR枠を非表示にする権利を有します。この場合においても、購入済みの広告費の返金は一切いたしません。</p>
          </section>

          <section>
            <h2>第3条（決済および返金）</h2>
            <p>本サービス内におけるPR枠等の決済は、クレジットカード決済代行サービス（Stripe）等を利用します。</p>
            <p>デジタル広告枠という商品の性質上、いかなる理由におきましても、購入手続き完了後のキャンセル・返品・返金には一切応じられません。</p>
          </section>

          <section>
            <h2>第4条（禁止事項）</h2>
            <p>ユーザーは、本サービスの利用にあたり、以下の行為をしてはなりません。</p>
            <ul>
              <li>当運営のサーバーやネットワークの機能を破壊したり、妨害したりする行為。</li>
              <li>自動化された手段（プログラム等）を用いて本サービスからデータを継続的に取得する行為。</li>
              <li>その他、当運営が不適切と判断する行為。</li>
            </ul>
          </section>

          <section>
            <h2>第5条（本サービスの提供の停止等）</h2>
            <p>当運営は、以下のいずれかの事由があると判断した場合、ユーザーに事前に通知することなく本サービスの全部または一部の提供を停止または中断することができるものとします。</p>
            <p>(1) 本サービスにかかるコンピュータシステムの保守点検または更新を行う場合<br />
              (2) 外部サービス（情報の取得元サイトや決済サービス等）の仕様変更、不具合、停止等により本サービスの提供が困難となった場合<br />
              (3) 地震、落雷、火災、停電または天災などの不可抗力により、本サービスの提供が困難となった場合<br />
              (4) コンピュータまたは通信回線等が事故により停止した場合<br />
              (5) その他、当運営が本サービスの提供が困難と判断した場合</p>
            <p>当運営は、本サービスの提供の停止または中断により、ユーザーまたは第三者が被ったいかなる不利益または損害についても、一切の責任を負わないものとします。</p>
          </section>

          <section>
            <h2>第6条（免責事項）</h2>
            <p>当運営は、本サービスに掲載される各公演の日程、時間、出演者、料金等の情報の正確性について、いかなる保証も行うものではありません（情報は各公式サイトの自動取得に基づきます）。ユーザーはご自身の責任において、各公式サイト等の一次情報をご確認の上、行動するものとします。</p>
            <p>公演の急な中止、延期等によってユーザーに生じた損害について、当運営は一切の責任を負いません。</p>
          </section>

          <section>
            <h2>第7条（反社会的勢力の排除）</h2>
            <p>ユーザーは、現在、暴力団、暴力団員、暴力団関係企業、総会屋等、社会運動等標ぼうゴロまたは特殊知能暴力集団等、その他これらに準ずる者（以下これらを「反社会的勢力」といいます。）に該当しないこと、および将来にわたっても該当しないことを確約するものとします。</p>
            <p>当運営は、ユーザーが反社会的勢力に該当すると判明した場合、何らの通知や催告をすることなく、本サービスの利用停止、取引の解除、その他必要な措置を講じることができるものとします。この場合、当運営はユーザーに対して一切の損害賠償責任を負わないものとします。</p>
          </section>

          <section>
            <h2>第8条（規約の変更）</h2>
            <p>当運営は、必要と判断した場合には、ユーザーに通知することなくいつでも本規約を変更することができるものとします。変更後の利用規約は、本サービス上に掲載した時点から効力を生じるものとします。</p>
          </section>

          <section>
            <h2>第9条（準拠法・裁判管轄）</h2>
            <p>本規約の解釈にあたっては、日本法を準拠法とします。</p>
            <p>本サービスに関して紛戦が生じた場合には、当運営の所在地を管轄する地方裁判所または簡易裁判所を専属的合意管轄とします。</p>
          </section>

          <div style={{ marginTop: '40px', padding: '20px', borderTop: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'right' }}>
            以上<br />
            制定日：2026年3月10日
          </div>
        </main>

        <footer style={{ padding: '40px 20px', textAlign: 'center' }}>
          <button className="primary-btn" onClick={() => navigateTo('/')} style={{ width: '200px' }}>
            ホームへ戻る
          </button>
        </footer>
      </div>
    );
  }

  // Privacy Policy View
  if (path === '/privacy') {
    return (
      <div className="terms-page">
        <header className="terms-header">
          <button className="back-btn" onClick={() => navigateTo('/')}>
            <ChevronDown style={{ transform: 'rotate(90deg)' }} size={24} /> ホームへ戻る
          </button>
          <h1>プライバシーポリシー</h1>
        </header>

        <main className="terms-content glass-panel">
          <p style={{ marginBottom: '24px', fontSize: '0.95rem', lineHeight: '1.6' }}>
            ドアチケ運営（以下、「当運営」といいます。）は、本ウェブサイト上で提供するサービス（以下、「本サービス」といいます。）における、ユーザーの個人情報の取扱いについて、以下のとおりプライバシーポリシー（以下、「本ポリシー」といいます。）を定めます。
          </p>

          <section>
            <h2>第1条（個人情報の収集方法）</h2>
            <p>当運営は、ユーザーが本サービスに関するお問い合わせや、PR枠（広告枠）の購入申請等を行う際に、氏名、メールアドレスなどの個人情報をお尋ねすることがあります。</p>
            <p>また、本サービスにおいて会員登録（ログイン）機能を利用する場合、LINEやGoogle等の外部サービスとの連携により、当該外部サービスから提供される識別子やプロフィール情報等を取得することがあります。</p>
            <p>なお、本サービス内でクレジットカード決済を行う場合、決済情報は決済代行会社（Stripe）が直接取得・管理し、当運営はユーザーのクレジットカード情報を一切保持しません。</p>
          </section>

          <section>
            <h2>第2条（個人情報を収集・利用する目的）</h2>
            <p>当運営が個人情報を収集・利用する目的は、以下のとおりです。</p>
            <ul>
              <li>本サービスの提供・運営のため</li>
              <li>ユーザーからのお問い合わせに回答するため（本人確認を行うことを含む）</li>
              <li>メンテナンス、重要なお知らせなど必要に応じたご連絡のため</li>
              <li>利用規約に違反したユーザーや、不正・不当な目的でサービスを利用しようとするユーザーの特定をし、ご利用をお断りするため</li>
              <li>広告枠（PR枠）購入者へのご案内、および取引の履行のため</li>
              <li>上記の利用目的に付随する目的</li>
            </ul>
          </section>

          <section>
            <h2>第3条（アクセス解析ツールおよびCookie・ローカルストレージ等の利用について）</h2>
            <p>本サービスでは、Googleによるアクセス解析ツール「Googleアナリティクス」を利用しています。このGoogleアナリティクスはトラフィックデータの収集のためにCookieを使用しています。このトラフィックデータは匿名で収集されており、個人を特定するものではありません。この機能はCookieを無効にすることで収集を拒否することが出来ますので、お使いのブラウザの設定をご確認ください。</p>
            <p>本サービスでは、ユーザーの利便性向上（「お気に入り」や「ブックマーク」機能の提供、および動画の報告状況の保持等）のため、ユーザーの端末のローカルストレージ（Web Storage）にデータを保存します。これらには個人を特定する情報は含まれません。また、外部サイトへのリンクには、当サイトからの送客実績を統計的に把握するための識別子（UTMパラメータ等）を付与する場合があります。これらについても個人を特定する情報は含まれません。</p>
          </section>

          <section>
            <h2>第4条（個人情報の第三者提供）</h2>
            <p>当運営は、次に掲げる場合を除いて、あらかじめユーザーの同意を得ることなく、第三者に個人情報を提供することはありません。ただし、個人情報保護法その他の法令で認められる場合を除きます。</p>
            <ul>
              <li>人の生命、身体または財産の保護のために必要がある場合であって、本人の同意を得ることが困難であるとき</li>
              <li>公衆衛生の向上または児童の健全な育成の推進のために特に必要がある場合であって、本人の同意を得ることが困難であるとき</li>
              <li>国の機関もしくは地方公共団体またはその委託を受けた者が法令の定める事務を遂行することに対して協力する必要がある場合であって、本人の同意を得ることにより当該事務の遂行に支障を及ぼすおそれがあるとき</li>
            </ul>
          </section>

          <section>
            <h2>第5条（外部リンク先の個人情報取扱いに関する免責）</h2>
            <p>本サービスには、外部サイト（各ライブハウスの公式サイト、チケット予約サイト等）へのリンクが含まれる場合があります。これら外部サイトにおける個人情報の収集・取扱い等につきましては、当運営は一切の責任を負いません。ユーザーご自身の責任において、各リンク先サイトのプライバシーポリシー等をご確認ください。</p>
          </section>

          <section>
            <h2>第6条（個人情報の開示・訂正・削除等）</h2>
            <p>ユーザーは、当運営の保有する自己の個人情報が誤った情報である場合、または情報の開示・削除を希望する場合、当運営が定める手続きにより、個人情報の開示、訂正、追加または削除を請求することができます。</p>
            <p>当運営は、ユーザーから前項の請求を受けてその請求に応じる必要があると判断した場合には、遅滞なく、当該個人情報の開示、訂正または削除等を行い、これをユーザーに通知します。</p>
          </section>

          <section>
            <h2>第7条（プライバシーポリシーの変更）</h2>
            <p>本ポリシーの内容は、法令その他本ポリシーに別段の定めのある事項を除いて、ユーザーに通知することなく変更することができるものとします。変更後のプライバシーポリシーは、本サービスに掲載したときから効力を生じるものとします。</p>
          </section>

          <section>
            <h2>第8条（個人情報取扱事業者の名称およびお問い合わせ窓口）</h2>
            <p>本ポリシーに関するお問い合わせ、および第6条に基づく個人情報の開示・訂正・削除等のご請求は、本サービス内のお問い合わせフォームよりお願いいたします。</p>
          </section>

          <div style={{ marginTop: '40px', padding: '20px', borderTop: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'right' }}>
            以上<br />
            制定日：2026年3月10日
          </div>
        </main>

        <footer style={{ padding: '40px 20px', textAlign: 'center' }}>
          <button className="primary-btn" onClick={() => navigateTo('/')} style={{ width: '200px' }}>
            ホームへ戻る
          </button>
        </footer>
      </div>
    );
  }

  return (
    <div className={`app-container ${isDropdownOpen || isMenuOpen ? 'modal-open' : ''}`}>
      <div className="top-section">
        <div className="top-section-inner">
          <header className="header" style={{ position: 'relative' }}>
            <div style={{ position: 'absolute', left: '15px', height: '100%', display: 'flex', alignItems: 'center' }}>
              <button
                onClick={() => { }}
                style={{ background: 'none', border: 'none', color: currentUser ? 'var(--accent-color)' : 'var(--text-secondary)', cursor: 'default', padding: '5px', display: 'flex', alignItems: 'center', position: 'relative' }}
                aria-label="アカウント（制限中）"
              >
                {currentUser && currentUser.photoURL ? (
                  <img src={currentUser.photoURL} alt="User" style={{ width: '26px', height: '26px', borderRadius: '50%' }} />
                ) : (
                  <User size={26} color={currentUser ? 'var(--accent-color)' : 'currentColor'} />
                )}
                <div style={{ position: 'absolute', bottom: '-2px', right: '-2px', background: 'var(--bg-color)', borderRadius: '50%', padding: '2px', border: '1px solid rgba(255,255,255,0.1)', display: 'flex' }}>
                  <Lock size={10} color="var(--text-secondary)" />
                </div>
              </button>
            </div>
            <h1 style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', width: '100%', height: '100%', gap: '6px', margin: 0, padding: 0, position: 'relative' }}>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <img 
                  src="/assets/logo.png" 
                  alt="ドアチケ" 
                  style={{ 
                    height: '48px', 
                    width: 'auto', 
                    display: 'block',
                    cursor: 'pointer'
                  }} 
                  onClick={() => setIsAboutModalOpen(true)}
                />
                {!isStandalone && (isInstallable || (isMobile && !isStandalone)) && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (deferredPrompt) {
                        handleInstallClick();
                      } else {
                        setIsInstallModalOpen(true);
                      }
                    }}
                    style={{
                      position: 'absolute',
                      right: '-45px',
                      background: 'var(--accent-color)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '12px',
                      padding: '4px 8px',
                      fontSize: '0.6rem',
                      fontWeight: 'bold',
                      animation: 'pulse 2s infinite',
                      cursor: 'pointer',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    INSTALL
                  </button>
                )}
              </div>
              <span style={{ 
                margin: 0, 
                fontSize: '0.7rem', 
                fontWeight: '600', 
                color: 'var(--text-secondary)',
                letterSpacing: '0.1em',
                opacity: 0.7,
                cursor: 'pointer'
              }}
              onClick={() => setIsAboutModalOpen(true)}
              >
                ドアチケ
              </span>
            </h1>
          </header>

          <div className="location-filters" style={{ padding: '10px 10px 10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div className="date-tabs">
                  <button
                    className={`tab-btn ${format(selectedDate, 'yyyy-MM-dd') === format(today, 'yyyy-MM-dd') ? 'active' : ''}`}
                    onClick={() => {
                      if (format(selectedDate, 'yyyy-MM-dd') !== format(today, 'yyyy-MM-dd')) {
                        setSelectedDate(today);
                      }
                    }}
                  >
                    今日
                  </button>
                  <button
                    className={`tab-btn ${format(selectedDate, 'yyyy-MM-dd') === format(tomorrow, 'yyyy-MM-dd') ? 'active' : ''}`}
                    onClick={() => {
                      if (format(selectedDate, 'yyyy-MM-dd') !== format(tomorrow, 'yyyy-MM-dd')) {
                        setSelectedDate(tomorrow);
                      }
                    }}
                  >
                    明日
                  </button>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    className={`filter-toggle-btn free-filter ${showOnlyFree ? 'active' : ''}`}
                    onClick={() => setShowOnlyFree(!showOnlyFree)}
                    title={showOnlyFree ? "すべて表示" : "0円チケットのみ表示"}
                  >
                    0チケ
                  </button>
                </div>
              </div>

              <div className="custom-dropdown" style={{ flexShrink: 0 }}>
                <button
                  className="dropdown-toggle"
                  onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                >
                  {selectedPrefecture === 'All' ? 'すべて' : selectedPrefecture === '愛知' ? '名古屋' : selectedPrefecture}
                  <ChevronDown size={16} />
                </button>

                {isDropdownOpen && (
                  <div className="dropdown-menu">
                    {[{ label: '東京', key: '東京' }, { label: '名古屋', key: '愛知' }, { label: '大阪', key: '大阪' }]
                      .filter(({ key }) => areasDict[key])
                      .map(({ label, key }) => (
                        <div
                          key={key}
                          className={`dropdown-item ${selectedPrefecture === key ? 'selected' : ''}`}
                          onClick={() => {
                            setSelectedPrefecture(key)
                            setSelectedArea('All')
                            setIsDropdownOpen(false)
                          }}
                        >
                          {label}
                        </div>
                      ))}
                  </div>
                )}
              </div>
            </div>

            {selectedPrefecture !== 'All' && areasDict[selectedPrefecture] && (
              <div className="filter-bar" style={{ padding: '0', margin: '0', paddingBottom: '2px' }}>
                <button
                  className={`filter-chip ${selectedArea === 'All' ? 'active' : ''}`}
                  onClick={() => setSelectedArea('All')}
                >
                  {selectedPrefecture}全域
                </button>
                {areasDict[selectedPrefecture].map(area => (
                  <button
                    key={area}
                    className={`filter-chip ${selectedArea === area ? 'active' : ''}`}
                    onClick={() => setSelectedArea(area)}
                  >
                    {area}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="main-content">
        <div className="section-title-stats" style={{ padding: '0', marginBottom: '10px', alignItems: 'center', display: 'flex' }}>
          <label className="favorites-checkbox-container" style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'default', fontSize: '0.86rem', color: 'var(--text-secondary)', userSelect: 'none', padding: '4px 0', marginRight: 'auto', position: 'relative', opacity: 0.7 }}>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <input
                type="checkbox"
                checked={showOnlyLiked}
                onChange={() => setShowOnlyLiked(!showOnlyLiked)}
                style={{ width: '16px', height: '16px', cursor: 'default' }}
              />
              <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', background: 'var(--bg-color)', borderRadius: '50%', width: '12px', height: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid rgba(255,255,255,0.2)' }}>
                <Lock size={8} color="var(--accent-color)" />
              </div>
            </div>
            <Heart size={14} fill="var(--accent-color)" color="var(--accent-color)" />
            <span style={{ fontWeight: '500', color: showOnlyLiked ? 'var(--text-primary)' : 'inherit' }}>Favorites</span>
          </label>

          <div className="stats-info" style={{ textAlign: 'right' }}>
            {selectedPrefecture === 'All' ? '全国' : (
              selectedArea === 'All' ? `${selectedPrefecture} 全域` : `${selectedPrefecture} ${selectedArea}`
            )}
            <span className="stats-count">
              {" "}{displayCount}件
            </span>
          </div>
        </div>
        <div className="event-list">
          {isLoading ? (
            <div className="empty-state">読み込み中...</div>
          ) : (
            <>
              {/* Today Regular */}
              {groups.todayRegular.length > 0 && (
                <div className="list-sub-header" style={{ marginTop: '0' }}>
                  <Sun size={16} fill="var(--accent-color)" color="var(--accent-color)" />
                  {format(selectedDate, 'M月d日')}（{['日', '月', '火', '水', '木', '金', '土'][selectedDate.getDay()]}）のイベント
                </div>
              )}
              {groups.todayRegular.map((evt, index) => (
                <EventCard 
                  key={evt.id} 
                  evt={evt} 
                  area={evt.livehouse.area} 
                  position={index + 1}
                  isAdmin={isAdmin}
                  handleToggleStaffPick={handleToggleStaffPick}
                  likedVenues={likedVenues}
                  toggleVenueLike={toggleVenueLike}
                  isEventBookmarked={isEventBookmarked}
                  toggleBookmark={toggleBookmark}
                  setVideoModal={setVideoModal}
                  reportedVideos={reportedVideos}
                  userPassType={userPassType}
                  handleCouponClick={() => userPassType ? setIsPassModalOpen(true) : setIsPurchaseModalOpen(true)}
                />
              ))}

              {/* Today Midnight */}
              {groups.todayMidnight.length > 0 && (
                <>
                  <div className="list-sub-header">
                    <Moon size={16} fill="var(--accent-color)" color="var(--accent-color)" />
                    {format(selectedDate, 'M月d日')}（{['日', '月', '火', '水', '木', '金', '土'][selectedDate.getDay()]}）深夜のイベント
                  </div>
                  {groups.todayMidnight.map((evt, index) => (
                    <EventCard 
                      key={evt.id} 
                      evt={evt} 
                      area={evt.livehouse.area} 
                      position={groups.todayRegular.length + index + 1}
                      isAdmin={isAdmin}
                      handleToggleStaffPick={handleToggleStaffPick}
                      likedVenues={likedVenues}
                      toggleVenueLike={toggleVenueLike}
                      isEventBookmarked={isEventBookmarked}
                      toggleBookmark={toggleBookmark}
                      setVideoModal={setVideoModal}
                      reportedVideos={reportedVideos}
                      userPassType={userPassType}
                      handleCouponClick={() => userPassType ? setIsPassModalOpen(true) : setIsPurchaseModalOpen(true)}
                    />
                  ))}
                </>
              )}

              {/* Tomorrow Events */}
              {groups.tomorrowEvents.length > 0 && (
                <>
                  <div className="list-sub-header">
                    <Calendar size={16} fill="var(--accent-color)" color="var(--accent-color)" />
                    明日のイベント
                  </div>
                  {groups.tomorrowEvents.map((evt, index) => (
                    <EventCard 
                      key={evt.id} 
                      evt={evt} 
                      area={evt.livehouse.area} 
                      position={index + 1}
                      isAdmin={isAdmin}
                      handleToggleStaffPick={handleToggleStaffPick}
                      likedVenues={likedVenues}
                      toggleVenueLike={toggleVenueLike}
                      isEventBookmarked={isEventBookmarked}
                      toggleBookmark={toggleBookmark}
                      setVideoModal={setVideoModal}
                      reportedVideos={reportedVideos}
                      userPassType={userPassType}
                      handleCouponClick={() => userPassType ? setIsPassModalOpen(true) : setIsPurchaseModalOpen(true)}
                    />
                  ))}
                </>
              )}

              {groups.todayRegular.length === 0 && groups.todayMidnight.length === 0 && (
                <div className="glass-panel empty-state">
                  <Calendar size={40} color="var(--text-secondary)" style={{ marginBottom: '15px', opacity: 0.5 }} />
                  <p>予定されているイベントがありません</p>
                </div>
              )}
            </>
          )}
        </div>

        {/* --- Footer --- */}
        <footer className="app-footer">
          <div className="footer-links" style={{ flexWrap: 'wrap', justifyContent: 'center', rowGap: '8px' }}>
            <button
              onClick={() => setIsAboutModalOpen(true)}
              className="footer-link"
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
            >
              システムについて
            </button>
            <span className="footer-divider">|</span>
            <a href="#" className="footer-link">お問い合わせ</a>
            <span className="footer-divider">|</span>
            <a
              href="/terms"
              className="footer-link"
              onClick={(e) => {
                e.preventDefault();
                navigateTo('/terms');
              }}
            >
              利用規約
            </a>
            <span className="footer-divider">|</span>
            <a
              href="/privacy"
              className="footer-link"
              onClick={(e) => {
                e.preventDefault();
                navigateTo('/privacy');
              }}
            >
              プライバシーポリシー
            </a>
          </div>
          <div className="footer-copyright">
            &copy; {new Date().getFullYear()} LIVE INFO HUB. All Rights Reserved.
          </div>
        </footer>

      </div>

      {/* --- Floating Navigation Bar --- */}
      {!isBookmarksModalOpen && !isPurchaseModalOpen && !isPassModalOpen && !isAuthModalOpen && (
        <div className="floating-nav-bar">
          <button className="nav-btn" onClick={scrollToTop} aria-label="トップへ戻る" title="トップへ戻る">
            <ArrowUp size={22} />
          </button>

          <div className="nav-divider" />

          <button
            className="nav-btn"
            onClick={() => {
              if (upcomingBookmarksCount > 0) setIsBookmarksModalOpen(true);
            }}
            style={{ position: 'relative', opacity: upcomingBookmarksCount > 0 ? 1 : 0.5 }}
            aria-label="気になるイベント"
            title="気になるイベント"
          >
            <Bookmark size={22} fill={upcomingBookmarksCount > 0 ? "currentColor" : "none"} />
            {upcomingBookmarksCount > 0 && (
              <span className="nav-badge">{upcomingBookmarksCount}</span>
            )}
          </button>

          <div className="nav-divider" />

          <button className="nav-btn" onClick={scrollToBottom} aria-label="一番下へ移動" title="一番下へ移動">
            <ArrowDown size={22} />
          </button>
        </div>
      )}

      {isBookmarksModalOpen && (
        <div className="modal-overlay" onClick={() => setIsBookmarksModalOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header" style={{ flexDirection: 'column', padding: '12px 20px 15px' }}>
              <div style={{ width: '40px', height: '5px', background: 'var(--control-border)', borderRadius: '3px', marginBottom: '15px' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                <h3><Bookmark size={18} fill="currentColor" style={{ position: 'relative', top: '1px' }} /> 気になるイベント</h3>
                <button className="close-btn" onClick={() => setIsBookmarksModalOpen(false)}>&times;</button>
              </div>
            </div>
            <div className="modal-body" ref={modalBodyRef}>
              <div className="event-list">
                {bookmarkedEvents.length > 0 ? (
                  sortedBookmarkDates.map(dateStr => {
                    const dateObj = new Date(dateStr)
                    return (
                      <div key={dateStr} style={{ marginBottom: '25px' }}>
                        <h4 style={{
                          margin: '0 0 12px 0',
                          padding: '6px 14px',
                          display: 'inline-block',
                          background: 'var(--control-bg)',
                          border: '1px solid var(--control-border)',
                          borderRadius: '20px',
                          fontSize: '0.85rem',
                          color: 'var(--text-primary)'
                        }}>
                          {isNaN(dateObj) ? dateStr : `${format(dateObj, 'M月d日')}（${['日', '月', '火', '水', '木', '金', '土'][dateObj.getDay()]}）`}
                        </h4>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                          {groupedBookmarks[dateStr].map(evt => (
                            <EventCard 
                              key={evt.id} 
                              evt={evt} 
                              area={evt.livehouse.area} 
                              isAdmin={isAdmin}
                              handleToggleStaffPick={handleToggleStaffPick}
                              likedVenues={likedVenues}
                              toggleVenueLike={toggleVenueLike}
                              isEventBookmarked={isEventBookmarked}
                              toggleBookmark={toggleBookmark}
                              setVideoModal={setVideoModal}
                              reportedVideos={reportedVideos}
                              userPassType={userPassType}
                              handleCouponClick={() => userPassType ? setIsPassModalOpen(true) : setIsPurchaseModalOpen(true)}
                            />
                          ))}
                        </div>
                      </div>
                    )
                  })
                ) : (
                  <div className="glass-panel empty-state" style={{ marginTop: '20px' }}>
                    <Bookmark size={40} color="var(--text-secondary)" style={{ marginBottom: '15px', opacity: 0.5 }} />
                    <p>ブックマークされたイベントはありません</p>
                  </div>
                )}
              </div>

              {/* Modal-specific Scroll Buttons (only when multiple items exist) */}
              {bookmarkedEvents.length > 2 && (
                <div className="floating-nav-bar modal-floating-nav">
                  <button className="nav-btn" onClick={scrollToModalTop} aria-label="モーダルのトップへ戻る" title="トップへ戻る">
                    <ArrowUp size={22} />
                  </button>

                  <div className="nav-divider" />

                  <button className="nav-btn" onClick={scrollToModalBottom} aria-label="モーダルの下へ移動" title="一番下へ移動">
                    <ArrowDown size={22} />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* --- PWA Install Modal (Standalone) --- */}
      {isInstallModalOpen && (
        <div className="modal-overlay" onClick={() => setIsInstallModalOpen(false)}>
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
            style={{ height: 'auto', maxHeight: '80vh' }}
          >
            <div className="modal-header">
              <h3><Smartphone size={20} /> ホーム画面に追加</h3>
              <button className="close-btn" onClick={() => setIsInstallModalOpen(false)}>&times;</button>
            </div>
            <div className="modal-body" style={{ padding: '32px 24px', color: 'var(--text-primary)' }}>
              <div style={{ textAlign: 'center', marginBottom: '24px' }}>
                <div style={{ 
                  background: 'var(--accent-color)', 
                  width: '64px', 
                  height: '64px', 
                  borderRadius: '16px', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center', 
                  margin: '0 auto 16px',
                  boxShadow: '0 8px 16px rgba(255, 51, 102, 0.2)' 
                }}>
                  <Download size={32} color="white" />
                </div>
                <h2 style={{ fontSize: '1.25rem', fontWeight: '800', marginBottom: '8px' }}>ドアチケをアプリとして使う</h2>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                  ブラウザの枠を消して、フルスクリーンの専用アプリのように快適に利用できます。
                </p>
              </div>

              {isInstallable && deferredPrompt ? (
                <button 
                  className="primary-btn" 
                  onClick={handleInstallClick}
                  style={{ width: '100%', height: '54px', borderRadius: '12px', fontSize: '1.1rem', fontWeight: '800', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
                >
                  <Download size={20} /> 今すぐインストール
                </button>
              ) : isIOS ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '16px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '12px', border: '1px solid var(--control-border)' }}>
                    <div style={{ background: 'var(--accent-color)', color: 'white', width: '28px', height: '28px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: '0.9rem', fontWeight: 'bold' }}>1</div>
                    <div style={{ fontSize: '0.95rem', lineHeight: '1.5' }}>
                      ブラウザの <strong>共有ボタン</strong> <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '2px 8px', background: 'rgba(255,255,255,0.1)', borderRadius: '6px', fontSize: '0.85rem' }}>📤</span> をタップ
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '16px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '12px', border: '1px solid var(--control-border)' }}>
                    <div style={{ background: 'var(--accent-color)', color: 'white', width: '28px', height: '28px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: '0.9rem', fontWeight: 'bold' }}>2</div>
                    <div style={{ fontSize: '0.95rem', lineHeight: '1.5' }}>
                      メニューから <strong>「ホーム画面に追加」</strong> を選択
                    </div>
                  </div>
                 {!isSafari && (
                   <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', padding: '0 8px', textAlign: 'center' }}>
                     ※「共有」ボタンはアドレスバー付近にある場合があります。
                   </div>
                 )}
                </div>
              ) : (
                <div style={{ padding: '20px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '12px', border: '1px dashed var(--control-border)', textAlign: 'center' }}>
                  <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                    ブラウザメニューの<br/><strong>「ホーム画面に追加」</strong><br/>または<strong>「インストール」</strong><br/>からアプリとして追加してください。
                  </p>
                </div>
              )}

              <button
                className="secondary-btn"
                onClick={() => setIsInstallModalOpen(false)}
                style={{ marginTop: '24px', width: '100%', height: '50px', borderRadius: '12px', fontSize: '1rem', fontWeight: '600', opacity: 0.7 }}
              >
                あとで
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --- Purchase Options Modal --- */}
      {isPurchaseModalOpen && (
        <div className="modal-overlay" onClick={() => setIsPurchaseModalOpen(false)}>
          <div className="modal-content purchase-modal" onClick={e => e.stopPropagation()} style={{ padding: '0' }}>
            <div style={{ position: 'relative', background: 'linear-gradient(135deg, var(--accent-color) 0%, #ff4b8b 100%)', padding: '16px 20px', color: 'white', borderTopLeftRadius: '20px', borderTopRightRadius: '20px', textAlign: 'center' }}>
              <button className="close-btn" onClick={() => setIsPurchaseModalOpen(false)} style={{ position: 'absolute', top: '15px', right: '15px', color: 'white' }}><X size={20} /></button>
              <h2 style={{ margin: '0', fontSize: '1.4rem' }}>DOOR TICKET PASS</h2>
            </div>

            <div style={{ padding: '20px' }}>
              <div style={{ background: 'rgba(255, 51, 102, 0.1)', border: '1px solid rgba(255, 51, 102, 0.3)', borderRadius: '12px', padding: '12px', marginBottom: '20px', textAlign: 'center' }}>
                <span style={{ fontWeight: 'bold', color: 'var(--accent-color)', fontSize: '0.95rem' }}>当日券を「前売料金」で購入可能！</span><br />
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Get Door Tickets at Advance Price</span>
              </div>

              <div className="purchase-card" style={{ marginBottom: '15px', border: '2px solid var(--accent-color)', borderRadius: '12px', padding: '15px', position: 'relative', overflow: 'hidden' }}>
                <div style={{ position: 'absolute', top: 0, right: 0, background: 'var(--accent-color)', color: 'white', fontSize: '0.7rem', fontWeight: 'bold', padding: '3px 10px', borderBottomLeftRadius: '8px' }}>おすすめ / Best for Locals</div>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '6px' }}><CheckCircle size={18} color="var(--accent-color)" />月額パス <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 'normal' }}>Monthly Sub</span></h3>
                <div style={{ fontSize: '1.4rem', fontWeight: 'bold', marginBottom: '10px' }}>¥380 <span style={{ fontSize: '0.8rem', fontWeight: 'normal', color: 'var(--text-secondary)' }}>/ 月(Month)</span></div>
                <button
                  style={{ width: '100%', padding: '12px', background: 'var(--accent-color)', color: 'white', border: 'none', borderRadius: '8px', fontWeight: 'bold', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}
                  onClick={() => { setUserPassType('monthly'); setIsPurchaseModalOpen(false); setIsPassModalOpen(true); }}
                >
                  <span>月額パスを購入する</span>
                  <span style={{ fontSize: '0.7rem', opacity: 0.9, fontWeight: 'normal' }}>Subscribe Monthly Pass</span>
                </button>
              </div>

              <div className="purchase-card" style={{ border: '1px solid var(--control-border)', borderRadius: '12px', padding: '15px' }}>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '6px' }}><Clock size={18} color="var(--text-secondary)" />24時間パス <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 'normal' }}>24h Pass</span></h3>
                <div style={{ fontSize: '1.4rem', fontWeight: 'bold', marginBottom: '10px' }}>¥250 <span style={{ fontSize: '0.8rem', fontWeight: 'normal', color: 'var(--text-secondary)' }}>/ 24h</span></div>
                <button
                  style={{ width: '100%', padding: '12px', background: 'var(--control-bg)', color: 'var(--text-primary)', border: '1px solid var(--control-border)', borderRadius: '8px', fontWeight: 'bold', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}
                  onClick={() => { setUserPassType('24h'); setIsPurchaseModalOpen(false); setIsPassModalOpen(true); }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><CreditCard size={16} /> Apple Pay / Google Pay で決済</div>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: 'normal' }}>Buy One-Time Pass</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* --- Active Pass Modal (Digital Door Ticket) --- */}
      {isPassModalOpen && (
        <div className="modal-overlay" style={{ backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}>
          <div style={{ position: 'relative', width: '90%', maxWidth: '380px', margin: 'auto' }}>
            {/* Close Button above card */}
            <div style={{ textAlign: 'right', marginBottom: '10px' }}>
              <button
                onClick={() => setIsPassModalOpen(false)}
                style={{ background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: '50%', width: '36px', height: '36px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: 'white', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Pass Card */}
            <div style={{
              background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
              borderRadius: '24px',
              padding: '30px 24px',
              color: 'white',
              boxShadow: '0 20px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1)',
              border: '1px solid rgba(255,255,255,0.05)',
              position: 'relative',
              overflow: 'hidden'
            }}>
              {/* Background Decoration */}
              <div style={{ position: 'absolute', top: '-50%', left: '-50%', width: '200%', height: '200%', background: 'radial-gradient(circle at center, rgba(255, 51, 102, 0.15) 0%, transparent 60%)', pointerEvents: 'none', animation: 'spin 20s linear infinite' }} />

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px', position: 'relative', zIndex: 1 }}>
                <div style={{ fontWeight: '900', fontStyle: 'italic', fontSize: '1.3rem', letterSpacing: '1px', color: 'var(--accent-color)', textShadow: '0 2px 4px rgba(0,0,0,0.5)' }}>
                  DOOR TICKET
                </div>
                <div style={{ background: 'rgba(255,255,255,0.1)', padding: '4px 12px', borderRadius: '20px', fontSize: '0.75rem', fontWeight: 'bold', textAlign: 'center' }}>
                  {userPassType === 'monthly' ? (
                    <>月額パス<br /><span style={{ fontSize: '0.6rem', fontWeight: 'normal' }}>Monthly Sub</span></>
                  ) : userPassType === '24h' ? (
                    <>24時間パス<br /><span style={{ fontSize: '0.6rem', fontWeight: 'normal' }}>24h Pass</span></>
                  ) : '有効なパス'}
                </div>
              </div>

              {/* CLOCK */}
              <div style={{ textAlign: 'center', margin: '40px 0', position: 'relative', zIndex: 1 }}>
                <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '5px', letterSpacing: '1px' }}>JST / 現在時刻</div>
                <div style={{
                  fontFamily: 'monospace',
                  fontSize: '2.8rem',
                  fontWeight: 'bold',
                  letterSpacing: '2px',
                  color: '#f8fafc',
                  textShadow: '0 0 10px rgba(255,255,255,0.3)'
                }}>
                  {format(passCurrentTime, 'HH:mm:ss')}
                </div>
                <div style={{ fontSize: '1rem', color: '#cbd5e1', marginTop: '5px' }}>
                  {format(passCurrentTime, 'yyyy/MM/dd (E)')}
                </div>
              </div>

              {/* Status */}
              <div style={{ background: 'rgba(34, 197, 94, 0.1)', border: '1px solid rgba(34, 197, 94, 0.3)', borderRadius: '12px', padding: '15px', display: 'flex', alignItems: 'center', gap: '12px', position: 'relative', zIndex: 1 }}>
                <div style={{ background: '#22c55e', minWidth: '40px', height: '40px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <CheckCircle size={24} color="white" />
                </div>
                <div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 'bold', color: '#4ade80', marginBottom: '2px' }}>有効なパスです / VALID PASS</div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: '1.3' }}>受付でこの画面を提示してください<br />Please show this screen at the entrance.</div>
                </div>
              </div>

              {/* Debug Reset Button */}
              <div style={{ textAlign: 'center', marginTop: '30px', position: 'relative', zIndex: 1 }}>
                <button
                  onClick={() => { setUserPassType(null); setIsPassModalOpen(false); }}
                  style={{ background: 'transparent', border: 'none', color: '#64748b', fontSize: '0.75rem', textDecoration: 'underline', cursor: 'pointer' }}
                >
                  デモ用：購入前の状態にリセット (Reset Demo)
                </button>
              </div>

            </div>
          </div>
        </div>
      )}
      {/* --- Auth Modal (Login / Register) --- */}
      {isAuthModalOpen && (
        <div className="modal-overlay" onClick={() => setIsAuthModalOpen(false)}>
          <div className="modal-content auth-modal" onClick={e => e.stopPropagation()} style={{ padding: '0', overflow: 'hidden', maxWidth: '400px', margin: '0 auto' }}>
            <div className="auth-header" style={{ position: 'relative', padding: '20px 20px 5px' }}>
              <button className="close-btn" onClick={() => setIsAuthModalOpen(false)} style={{ position: 'absolute', top: '15px', right: '15px' }}><X size={24} /></button>
              <h2 style={{ textAlign: 'center', margin: '15px 0 10px', fontSize: '1.4rem' }}>
                {currentUser ? 'アカウント情報' : (authMode === 'login' ? 'ログイン' : '新規登録')}
              </h2>
              {!currentUser && (
                <div className="auth-tabs" style={{ display: 'flex', borderBottom: '1px solid var(--control-border)', marginBottom: '15px' }}>
                  <button
                    style={{ flex: 1, padding: '10px', border: 'none', background: 'none', borderBottom: authMode === 'login' ? '2px solid var(--accent-color)' : 'none', color: authMode === 'login' ? 'var(--accent-color)' : 'var(--text-secondary)', fontWeight: authMode === 'login' ? 'bold' : 'normal', cursor: 'pointer' }}
                    onClick={() => { setAuthMode('login'); setAuthError(''); }}
                  >
                    ログイン
                  </button>
                  <button
                    style={{ flex: 1, padding: '10px', border: 'none', background: 'none', borderBottom: authMode === 'signup' ? '2px solid var(--accent-color)' : 'none', color: authMode === 'signup' ? 'var(--accent-color)' : 'var(--text-secondary)', fontWeight: authMode === 'signup' ? 'bold' : 'normal', cursor: 'pointer' }}
                    onClick={() => { setAuthMode('signup'); setAuthError(''); }}
                  >
                    新規登録
                  </button>
                </div>
              )}
            </div>

            {currentUser ? (
              <div className="auth-body" style={{ padding: '0 25px 30px', textAlign: 'center' }}>
                <div style={{ marginBottom: '25px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  {currentUser.photoURL ? (
                    <img src={currentUser.photoURL} alt="Profile" style={{ width: '70px', height: '70px', borderRadius: '50%', marginBottom: '15px' }} />
                  ) : (
                    <div style={{ width: '70px', height: '70px', borderRadius: '50%', background: 'var(--control-bg)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '15px' }}>
                      <User size={35} color="var(--text-secondary)" />
                    </div>
                  )}
                  <p style={{ fontWeight: 'bold', fontSize: '1.2rem', margin: '0 0 5px' }}>{currentUser.displayName || 'ユーザー'}</p>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', margin: 0 }}>{currentUser.email}</p>
                </div>
                <button
                  className="auth-submit-btn"
                  onClick={handleSignOut}
                  style={{ background: 'var(--control-bg)', color: 'var(--text-primary)', border: '1px solid var(--control-border)', boxShadow: 'none' }}
                >
                  ログアウト
                </button>
              </div>
            ) : (
              <div className="auth-body" style={{ padding: '0 25px 30px' }}>
                {authError && (
                  <div style={{ background: 'rgba(255, 51, 102, 0.1)', color: 'var(--accent-color)', padding: '10px', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '15px', textAlign: 'center' }}>
                    {authError}
                  </div>
                )}

                <div className="auth-social-buttons" style={{ display: 'flex', flexDirection: 'column', gap: '15px', marginBottom: '25px' }}>
                  {/* Google Login Button */}
                  <button className="social-btn google-btn" onClick={handleGoogleLogin}>
                    <svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" className="social-icon"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.7 17.74 9.5 24 9.5z"></path><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"></path><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"></path><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"></path><path fill="none" d="M0 0h48v48H0z"></path></svg>
                    <span>Continue with Google</span>
                  </button>

                  {/* Apple Login Button */}
                  <button className="social-btn apple-btn" onClick={handleAppleLogin}>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512" className="social-icon"><path d="M318.7 268.7c-.2-36.7 16.4-64.4 50-84.8-18.8-26.9-47.2-41.7-84.7-44.6-35.5-2.8-74.3 20.7-88.5 20.7-15 0-49.4-19.7-76.4-19.7C63.3 141.2 4 184.8 4 273.5q0 39.3 14.4 81.2c12.8 36.7 59 126.7 107.2 125.2 25.2-.6 43-17.9 75.8-17.9 31.8 0 48.3 17.9 76.4 17.9 48.6-.7 90.4-82.5 102.6-119.3-65.2-30.7-61.7-90-61.7-91.9zm-56.6-164.2c27.3-32.4 24.8-61.9 24-72.5-24.1 1.4-52 16.4-67.9 34.9-17.5 19.8-27.8 44.3-25.6 71.9 26.1 2 49.9-11.4 69.5-34.3z" /></svg>
                    <span>Continue with Apple</span>
                  </button>
                </div>

                <div className="auth-separator">
                  <span>またはメールアドレスで{authMode === 'login' ? 'ログイン' : '登録'}</span>
                </div>

                <form className="auth-form" onSubmit={authMode === 'login' ? handleEmailLogin : handleEmailSignUp}>
                  {authMode === 'signup' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                      <input
                        type="text"
                        placeholder="名前（ニックネーム）"
                        className="auth-input"
                        value={displayName}
                        onChange={e => setDisplayName(e.target.value)}
                        maxLength={10}
                        required
                      />
                      <span style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', textAlign: 'right', paddingRight: '12px' }}>
                        {displayName.length}/10
                      </span>
                    </div>
                  )}
                  <input type="email" placeholder="メールアドレス" className="auth-input" value={email} onChange={e => setEmail(e.target.value)} required />
                  <input type="password" placeholder="パスワード" className="auth-input" value={password} onChange={e => setPassword(e.target.value)} required />
                  <button type="submit" className="auth-submit-btn">
                    {authMode === 'login' ? 'ログイン' : 'アカウント作成'}
                  </button>
                </form>

                <div style={{ textAlign: 'center', marginTop: '20px', fontSize: '0.85rem' }}>
                  {authMode === 'login' ? (
                    <>
                      <a href="#" style={{ color: 'var(--accent-color)', textDecoration: 'none' }} onClick={(e) => { e.preventDefault(); setAuthError('パスワード再設定メール機能は準備中です'); }}>パスワードをお忘れですか？</a>
                      <p style={{ marginTop: '18px', color: 'var(--text-secondary)' }}>
                        アカウントをお持ちでないですか？ <br />
                        <a href="#" style={{ color: 'var(--accent-color)', textDecoration: 'none', fontWeight: 'bold', display: 'inline-block', marginTop: '5px' }} onClick={(e) => { e.preventDefault(); setAuthMode('signup'); }}>新規登録はこちら</a>
                      </p>
                    </>
                  ) : (
                    <p style={{ color: 'var(--text-secondary)' }}>
                      既にアカウントをお持ちですか？ <br />
                      <a href="#" style={{ color: 'var(--accent-color)', textDecoration: 'none', fontWeight: 'bold', display: 'inline-block', marginTop: '5px' }} onClick={(e) => { e.preventDefault(); setAuthMode('login'); }}>ログインはこちら</a>
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* YouTube Preview - 中央モーダル */}
      {videoModal && (
        <>
          {/* 背景オーバーレイ（クリックで閉じる） */}
          <div
            onClick={() => setVideoModal(null)}
            style={{
              position: 'fixed', inset: 0,
              background: 'rgba(0,0,0,0.65)',
              zIndex: 1999,
            }}
          />
          {/* モーダル本体 */}
          <div
            style={{
              position: 'fixed',
              top: '50%', left: '50%',
              transform: 'translate(-50%, -50%)',
              width: 'calc(100% - 32px)', maxWidth: '480px',
              zIndex: 2000,
              background: '#1a1a2e',
              borderRadius: '16px',
              overflow: 'hidden',
              boxShadow: '0 16px 48px rgba(0,0,0,0.8)',
              border: '1px solid rgba(255,255,255,0.12)',
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
              <span style={{ fontWeight: '600', fontSize: '0.85rem', color: '#ffffff' }}>{videoModal.artistName}</span>
              <button onClick={() => setVideoModal(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#cccccc', display: 'flex', alignItems: 'center' }}>
                <X size={18} />
              </button>
            </div>

            {/* Player body */}
            {videoModal.loading ? (
              <div style={{ padding: '30px', textAlign: 'center', color: '#aaaaaa', fontSize: '0.85rem' }}>検索中...</div>
            ) : videoModal.isConfirming ? (
              <div style={{ padding: '40px 20px', textAlign: 'center' }}>
                <div style={{ color: '#ffffff', fontWeight: 'bold', fontSize: '1rem', marginBottom: '15px' }}>
                  この動画は間違っていますか？
                </div>
                <div style={{ color: '#cbd5e1', fontSize: '0.85rem', lineHeight: '1.5', marginBottom: '25px' }}>
                  報告すると、運営で動画の修正を行います。<br />
                  （一時的に動画が非表示になります）
                </div>
                <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
                  <button
                    onClick={() => setVideoModal(prev => ({ ...prev, isConfirming: false }))}
                    style={{
                      padding: '10px 24px',
                      background: 'rgba(255,255,255,0.05)',
                      color: '#ffffff',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '8px',
                      fontSize: '0.85rem',
                      cursor: 'pointer'
                    }}
                  >
                    キャンセル
                  </button>
                  <button
                    onClick={() => handleReportVideo(true)}
                    disabled={isReporting}
                    style={{
                      padding: '10px 24px',
                      background: isReporting ? '#ccc' : 'var(--accent-color)',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '0.85rem',
                      fontWeight: 'bold',
                      cursor: isReporting ? 'not-allowed' : 'pointer',
                      boxShadow: isReporting ? 'none' : '0 4px 12px rgba(255, 51, 102, 0.3)'
                    }}
                  >
                    {isReporting ? '送信中...' : '報告する'}
                  </button>
                </div>
              </div>
            ) : videoModal.videoId && !videoModal.reported ? (
              <>
                <iframe
                  width="100%"
                  src={`https://www.youtube.com/embed/${videoModal.videoId}?autoplay=1`}
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                  style={{ display: 'block', border: 'none', aspectRatio: '16/9' }}
                />
                {/* チケットリンク */}
                {videoModal.ticketUrl && (
                  <a
                    href={addUtmParams(videoModal.ticketUrl, 'video_modal_link')}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                      padding: '10px 14px',
                      background: 'transparent',
                      color: '#6ab4f5', textDecoration: 'none',
                      fontSize: '0.82rem', fontWeight: '500',
                      borderTop: '1px solid rgba(255,255,255,0.1)',
                      border: '1px solid rgba(106,180,245,0.3)',
                      margin: '0 14px 12px',
                      borderRadius: '8px',
                      marginTop: '10px',
                    }}
                  >
                    🎫 チケットを確認する
                  </a>
                )}
                {/* 報告ボタン */}
                <button
                  onClick={() => handleReportVideo()}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                    padding: '8px 14px',
                    background: 'transparent',
                    color: '#cbd5e1', border: 'none',
                    fontSize: '0.75rem', cursor: 'pointer',
                    width: '100%', marginBottom: '10px'
                  }}
                >
                  <Flag size={14} /> この動画は間違っていますか？報告する
                </button>
              </>
            ) : videoModal.reported ? (
              <div style={{ padding: '60px 20px', textAlign: 'center' }}>
                <div style={{ background: 'rgba(34, 197, 94, 0.1)', width: '48px', height: '48px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 15px' }}>
                  <CheckCircle size={28} color="#22c55e" />
                </div>
                <div style={{ color: '#ffffff', fontWeight: 'bold', fontSize: '1rem', marginBottom: '8px' }}>報告を受け付けました</div>
                <div style={{ color: '#cbd5e1', fontSize: '0.85rem', lineHeight: '1.5' }}>
                  ご報告ありがとうございます。<br />
                  運営で確認し、修復いたします。
                </div>
              </div>
            ) : (
              <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                動画が見つかりませんでした
              </div>
            )}
          </div>
        </>
      )}
      {/* --- About Modal --- */}
      {isAboutModalOpen && (
        <div className="modal-overlay" onClick={() => setIsAboutModalOpen(false)}>
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
            style={{ height: 'auto', maxHeight: '90vh' }}
          >
            <div className="modal-header">
              <h3><BookOpen size={20} /> DOORTIKE.</h3>
              <button className="close-btn" onClick={() => setIsAboutModalOpen(false)}>&times;</button>
            </div>
            <div className="modal-body" style={{ padding: '32px 24px', color: 'var(--text-primary)' }}>
              {/* Header Group */}
              <div className="about-header-group">
                <h2 className="about-main-title">今すぐ、ライブハウスへ。</h2>
                <p className="about-sub-title">
                  ドアチケは、 あなたの「突発的な衝動」を後押しする{"\n"}
                  直前特化のライブディグアプリです。
                </p>
              </div>

              {/* Feature Cards */}
              <div className="about-features-container">
                <div className="about-feature-card theme-blue">
                  <div className="about-icon-circle">
                    <Briefcase size={32} strokeWidth={2.5} />
                  </div>
                  <div className="about-card-content">
                    <div className="about-card-label">仕事が早く終わった夜に</div>
                    <div className="about-card-desc">平日19時、スーツのままで。</div>
                  </div>
                </div>

                <div className="about-feature-card theme-green">
                  <div className="about-icon-circle">
                    <Plane size={32} strokeWidth={2.5} />
                  </div>
                  <div className="about-card-content">
                    <div className="about-card-label">出張や旅行の空き時間に</div>
                    <div className="about-card-desc">観光ガイドにない、今夜限りの熱狂へ。</div>
                  </div>
                </div>

                <div className="about-feature-card theme-red">
                  <div className="about-icon-circle">
                    <Zap size={32} strokeWidth={2.5} />
                  </div>
                  <div className="about-card-content">
                    <div className="about-card-label">イヤホン越しの音じゃ物足りない夜に</div>
                    <div className="about-card-desc">プレイリストより、今夜のセットリストを。</div>
                  </div>
                </div>
              </div>

              {/* Note / Admin sections (existing, slightly adjusted margins) */}
              <div style={{ marginTop: '48px' }}>
                <div style={{ marginBottom: '24px', padding: '16px', borderRadius: '12px', background: 'rgba(255, 204, 0, 0.1)', border: '1px solid rgba(255, 204, 0, 0.3)' }}>
                  <h4 style={{ fontSize: '1rem', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: '700' }}>
                    ⚠️ 前売り券を買うファンへのリスペクト
                  </h4>
                  <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                    当アプリは「前売り券を買ってくれる熱心なファン」を最大限リスペクトしています。{"\n"}
                    当日の突発的なディグ（発掘）をサポートするツールですが、あらかじめ予定が立つライブにつきましては、各リンクより前売り券やバンド予約（取り置き）のご利用を強く推奨しております。
                  </p>
                </div>

                <div style={{ padding: '16px', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.05)', border: '1px solid var(--control-border)' }}>
                  <h4 style={{ fontSize: '1rem', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: '700' }}>
                    🏢 各ライブハウス様・出演者関係者の皆様へ
                  </h4>
                  <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                    当サイトの公演情報は、各ライブハウスの公式サイトよりシステムが自動収集して掲載しております。{"\n"}
                    掲載費用等は一切いただいておりませんが、掲載内容の修正・削除をご希望の場合は、お手数ですが[お問い合わせフォーム]よりご連絡ください。{"\n"}
                    迅速に対応いたします。
                  </p>
                </div>
              </div>


              <button
                className="primary-btn"
                onClick={() => setIsAboutModalOpen(false)}
                style={{ marginTop: '40px', width: '100%', height: '54px', borderRadius: '27px', fontSize: '1.1rem', fontWeight: '800' }}
              >
                閉じる
              </button>
            </div>
          </div>
        </div>
      )}
      {/* --- Mobile Install Banner --- */}
      {showInstallBanner && !isStandalone && isMobile && (
        <div className="mobile-install-banner">
          <button 
            className="install-banner-close" 
            onClick={() => {
              setShowInstallBanner(false);
              localStorage.setItem('installBannerDismissed', 'true');
            }}
          >
            <X size={14} />
          </button>
          <div className="install-banner-content">
            <div className="install-banner-icon">
              <Download size={22} />
            </div>
            <div className="install-banner-text">
              <h4>ホーム画面に追加</h4>
              <p>アプリとして快適に利用できます</p>
            </div>
          </div>
          <button 
            className="install-banner-btn"
            onClick={() => setIsInstallModalOpen(true)}
          >
            追加する
          </button>
        </div>
      )}
    </div>
  )
}

export default App

// --- Helper Functions and Sub-components (outside App to avoid recreation on re-render) ---

const addUtmParams = (url, campaign) => {
  if (!url) return url;
  try {
    const urlObj = new URL(url);
    urlObj.searchParams.set('utm_source', 'doortike');
    urlObj.searchParams.set('utm_medium', 'referral');
    urlObj.searchParams.set('utm_campaign', campaign || 'general');
    return urlObj.toString();
  } catch (e) {
    if (typeof url === 'string' && url.startsWith('http')) {
      const separator = url.includes('?') ? '&' : '?';
      return `${url}${separator}utm_source=doortike&utm_medium=referral&utm_campaign=${campaign || 'general'}`;
    }
    return url;
  }
};

const isEventHappening = (evt) => {
  if (!evt.start_time || !evt.date) return false;
  const todayStr = format(new Date(), 'yyyy-MM-dd');
  if (evt.date !== todayStr) return false;

  try {
    const [hours, minutes] = evt.start_time.split(':').map(Number);
    if (isNaN(hours) || isNaN(minutes)) return false;
    const startTime = new Date();
    startTime.setHours(hours, minutes, 0, 0);
    const now = new Date();
    const diffMs = now - startTime;
    const diffHours = diffMs / (1000 * 60 * 60);
    return diffHours >= 0 && diffHours <= 3;
  } catch (e) {
    return false;
  }
};

const EventCard = ({ 
  evt, 
  area, 
  position, 
  isAdmin, 
  handleToggleStaffPick, 
  likedVenues, 
  toggleVenueLike, 
  isEventBookmarked, 
  toggleBookmark, 
  setVideoModal, 
  reportedVideos, 
  userPassType, 
  handleCouponClick 
}) => {
  if (!evt || !evt.livehouse) return null;
  const happening = isEventHappening(evt);
  
  const eventLabel = `${evt.date}_${evt.livehouse.name}_${evt.title}`;
  const { ref, inView } = useInView({ triggerOnce: true, threshold: 0.1 });

  useEffect(() => {
    if (inView) {
      ReactGA.event({
        category: "EventCard",
        action: "Impression",
        label: eventLabel,
        area: area,
        position: position,
        is_pr: evt.is_pr || false
      });
    }
  }, [inView, eventLabel, area, position, evt.is_pr]);

  const handleVideoClick = (perfInfo) => {
    ReactGA.event({
      category: "Engagement",
      action: "Play_Video",
      label: eventLabel,
      artist: perfInfo.name,
      area: area,
      position: position
    });
    
    setVideoModal({ 
      artistName: perfInfo.name, 
      loading: false, 
      videoId: perfInfo.youtube_id, 
      reported: reportedVideos.includes(perfInfo.name), 
      eventId: evt.id,
      ticketUrl: evt.ticket_url ? addUtmParams(evt.ticket_url, 'video_modal_ticket') : null 
    });
  };

  const handleTicketClick = () => {
    ReactGA.event({
      category: "Conversion",
      action: "Click_Ticket",
      label: eventLabel,
      area: area,
      position: position,
      is_pr: evt.is_pr || false
    });
  };

  return (
    <div 
      ref={ref}
      className={`glass-panel event-card ${evt.is_pr ? 'pr-card' : ''} ${evt.pickup_type === 'staff' && !evt.is_pr ? 'staff-pick-card' : ''} ${happening ? 'is-happening' : ''}`} 
      style={{ display: 'flex', flexDirection: 'row', overflow: 'visible', padding: 0, position: 'relative' }}
    >
        <div className="card-badge-container">
          {(evt.pickup_type === 'hot' || (evt.bookmark_count >= 5)) && <span className="card-badge hot-badge"><Flame size={12} style={{marginRight: '2px'}} /> HOT</span>}
        </div>

        {isAdmin && (
          <button 
            className={`admin-pickup-btn ${evt.pickup_type === 'staff' ? 'active' : ''}`}
            onClick={(e) => handleToggleStaffPick(e, evt)}
            title="STAFF PICK の切り替え"
          >
            👑
          </button>
        )}

        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', padding: '16px 15px' }}>
          <div className="event-header">
            <div className="venue-info">
              <div className="venue-name-row" style={{ flexWrap: 'wrap', rowGap: '4px', alignItems: 'center' }}>
                <MapPin size={15} style={{ flexShrink: 0, color: 'var(--accent-color)', marginRight: '2px' }} />
                {evt.venues && evt.venues.length > 1 ? (
                  evt.venues.map((venue, idx) => (
                    <div key={idx} style={{ display: 'flex', alignItems: 'center' }}>
                      {idx > 0 && <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', margin: '0 4px' }}>/</span>}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                        <a
                          href={addUtmParams(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name)}`, 'card_map_link')}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="venue-link"
                          style={{ lineHeight: 1, paddingBottom: '1px', fontWeight: 700, fontSize: '0.85rem' }}
                        >
                          {venue.name}
                        </a>
                        <div style={{ display: 'flex', alignItems: 'center', transform: 'translateY(-2px)' }}>
                          <button
                            className={`icon-btn-small ${likedVenues.includes(venue.id) ? 'active' : ''}`}
                            onClick={(e) => { e.stopPropagation(); toggleVenueLike(venue.id); }}
                            title="お気に入りライブハウスに追加"
                          >
                            <Heart fill={likedVenues.includes(venue.id) ? "var(--accent-color)" : "none"} size={16} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <a
                      href={addUtmParams(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(evt.livehouse.name)}`, 'card_map_link')}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="venue-link"
                      style={{ lineHeight: 1, paddingBottom: '1px', fontWeight: 700, fontSize: '0.85rem' }}
                    >
                      {evt.livehouse.name}
                    </a>
                    <div style={{ display: 'flex', alignItems: 'center', marginLeft: '4px', transform: 'translateY(-2px)' }}>
                      <button
                        className={`icon-btn-small ${likedVenues.includes(evt.livehouse.id) ? 'active' : ''}`}
                        onClick={(e) => { e.stopPropagation(); toggleVenueLike(evt.livehouse.id); }}
                        title="お気に入りライブハウスに追加"
                      >
                        <Heart fill={likedVenues.includes(evt.livehouse.id) ? "var(--accent-color)" : "none"} size={16} />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <h3 className="event-title">
            <a
              href={evt.ticket_url ? addUtmParams(evt.ticket_url, 'card_title_ticket') : addUtmParams(`https://www.google.com/search?q=${encodeURIComponent(`${evt.livehouse.name} ${evt.title} チケット`)}`, 'card_title_google_search')}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => {
                e.stopPropagation();
                handleTicketClick();
              }}
              className="event-link"
              title={evt.ticket_url ? "チケット購入（外部サイト）" : "チケットを検索（Google）"}
            >
              {evt.title}
            </a>
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.75rem', color: 'var(--text-primary)', marginTop: '4px', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={12} style={{ flexShrink: 0, color: 'var(--accent-color)' }} />
              <span>
                {isEventHappening(evt) ? (
                  <>
                    <span style={{ color: '#FF3366', fontWeight: '800', fontSize: '0.75rem', marginRight: '8px' }}>
                      <span style={{ fontSize: '0.8rem', marginRight: '2px', display: 'inline-block' }}>🔴</span> 開催中
                    </span>
                    START {evt.start_time}
                  </>
                ) : (
                  <>OPEN {evt.open_time} / START {evt.start_time}</>
                )}
              </span>
            </div>
            {evt.price_info && (
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '4px' }}>
                <Ticket size={12} style={{ flexShrink: 0, marginTop: '1px', color: 'var(--accent-color)' }} />
                <span className="event-price-info">{evt.price_info}</span>
              </div>
            )}
          </div>

          <p className="event-performers">
            {(() => {
              const infoList = evt.artists_data && evt.artists_data.length > 0
                ? evt.artists_data.map(item => ({ 
                    name: item.name, 
                    youtube_id: item.youtube_id 
                  }))
                : (evt.performers
                  ? evt.performers.split(/[、,／/\n]\s*/).filter(p => p.trim()).map(p => ({ name: p.trim(), youtube_id: null }))
                  : []);

              return infoList.map((perfInfo, index) => (
                <span key={index}>
                  {perfInfo.youtube_id ? (
                    <span
                      className="performer-link"
                      onClick={() => handleVideoClick(perfInfo)}
                    >
                      {perfInfo.name}
                    </span>
                  ) : (
                    <span className="performer-name">{perfInfo.name}</span>
                  )}
                  {index < infoList.length - 1 ? <span style={{ margin: '0 6px', color: 'var(--text-secondary)' }}>/</span> : ''}
                </span>
              ));
            })()}
          </p>

          <div className="action-buttons" style={{ marginTop: 'auto', paddingTop: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
            {evt.livehouse.drink_fee && (
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '2px 8px',
                background: 'var(--control-bg)',
                color: 'var(--text-secondary)',
                borderRadius: '12px',
                fontSize: '0.8rem',
                fontWeight: '600',
                border: '1px solid var(--control-border)',
                marginRight: 'auto'
              }}>
                1D ¥{evt.livehouse.drink_fee}
              </span>
            )}

            {(evt.livehouse.blog_url || evt.coupon_url) && (
              <div style={{ 
                display: 'flex', 
                gap: '8px', 
                alignItems: 'center', 
                marginLeft: evt.livehouse.drink_fee ? '0' : 'auto',
                marginRight: '30px'
              }}>
                {evt.livehouse.blog_url && (
                  <a
                    href={addUtmParams(evt.livehouse.blog_url, 'card_blog_link')}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="icon-btn"
                    title="関連ブログ記事を読む"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--text-secondary)',
                      textDecoration: 'none',
                      padding: '0',
                      width: '36px',
                      height: '36px',
                      background: 'rgba(var(--text-secondary-rgb), 0.05)',
                      borderRadius: '50%',
                      border: '1px solid var(--control-border)',
                      transition: 'all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
                      position: 'relative'
                    }}
                    onMouseOver={(e) => {
                      e.currentTarget.style.background = 'rgba(var(--text-secondary-rgb), 0.1)';
                      e.currentTarget.style.transform = 'scale(1.15)';
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.background = 'rgba(var(--text-secondary-rgb), 0.05)';
                      e.currentTarget.style.transform = 'scale(1)';
                    }}
                  >
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <BookOpen size={20} />
                      <ExternalLink size={10} style={{ position: 'absolute', top: '-6px', right: '-8px' }} />
                    </div>
                  </a>
                )}
                {evt.coupon_url && (
                  <button
                    onClick={(e) => handleCouponClick(e, evt)}
                    className="icon-btn"
                    title={userPassType ? "ドアチケパスを表示" : "お得なパスポートを見る"}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: userPassType ? 'var(--accent-color)' : 'var(--text-secondary)',
                      textDecoration: 'none',
                      padding: '0',
                      width: '36px',
                      height: '36px',
                      background: userPassType ? 'rgba(255, 51, 102, 0.08)' : 'rgba(var(--text-secondary-rgb), 0.05)',
                      borderRadius: '50%',
                      border: userPassType ? '1px solid var(--accent-color)' : '1px solid var(--control-border)',
                      cursor: 'pointer',
                      transition: 'all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
                      position: 'relative'
                    }}
                    onMouseOver={(e) => {
                      e.currentTarget.style.background = userPassType ? 'rgba(255, 51, 102, 0.12)' : 'rgba(var(--text-secondary-rgb), 0.1)';
                      e.currentTarget.style.transform = 'scale(1.15)';
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.background = userPassType ? 'rgba(255, 51, 102, 0.08)' : 'rgba(var(--text-secondary-rgb), 0.05)';
                      e.currentTarget.style.transform = 'scale(1)';
                    }}
                  >
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Ticket size={20} />
                    </div>
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        <div style={{
          width: '120px',
          flexShrink: 0,
          borderRadius: '0',
          overflow: 'visible',
          backgroundColor: 'var(--control-bg)',
          position: 'relative',
          zIndex: 5
        }}>
          <div style={{
            width: '100%',
            height: '100%',
            overflow: 'hidden',
            borderRadius: '0 var(--surface-radius) var(--surface-radius) 0',
            position: 'relative'
          }}>
            {evt.image_url ? (
              <img
                src={evt.image_url}
                alt="Thumbnail"
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                loading="lazy"
              />
            ) : (
              <div className="no-image-placeholder">NO IMAGE</div>
            )}
          </div>
          
          <button
            onClick={(e) => { e.stopPropagation(); toggleBookmark(evt); }}
            title="気になるイベントに保存"
            style={{
              position: 'absolute',
              top: '12px',
              right: '12px',
              padding: '8px',
              background: 'rgba(255, 255, 255, 0.85)',
              backdropFilter: 'blur(8px)',
              WebkitBackdropFilter: 'blur(8px)',
              borderRadius: '50%',
              border: '1px solid rgba(255,255,255,1)',
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s',
              cursor: 'pointer'
            }}
            onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.1)'}
            onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
          >
            <Bookmark fill={isEventBookmarked(evt.id) ? "var(--accent-color)" : "none"} color={isEventBookmarked(evt.id) ? "var(--accent-color)" : "#475569"} size={18} />
          </button>
        </div>
    </div>
  );
};
