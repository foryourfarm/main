'use client';

import { useEffect, useState } from 'react';
import styles from './Header.module.css';

export default function Header() {
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [userName, setUserName] = useState('농사인');
  const [userLocation, setUserLocation] = useState('지역 미지정');

  useEffect(() => {
    // 다크모드 복원
    const saved = localStorage.getItem('darkMode');
    if (saved === 'true') {
      setIsDarkMode(true);
      document.body.classList.add('dark-mode');
    }

    // 사용자 정보 복원
    const user = localStorage.getItem('userInfo');
    if (user) {
      try {
        const parsed = JSON.parse(user);
        setUserName(parsed.name || '농사인');
        setUserLocation(parsed.location || '지역 미지정');
      } catch {}
    }
  }, []);

  const toggleDarkMode = () => {
    const newMode = !isDarkMode;
    setIsDarkMode(newMode);
    localStorage.setItem('darkMode', String(newMode));
    if (newMode) {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }
  };

  return (
    <header className={styles.header}>
      <div className={styles.logo}>🌾 For Your Farm</div>
      <div className={styles.headerRight}>
        <div className={styles.userInfo}>
          <div className={styles.userName}>{userName}</div>
          <div className={styles.userLocation}>{userLocation}</div>
        </div>
        <button className={styles.darkToggle} onClick={toggleDarkMode}>
          {isDarkMode ? '☀️' : '🌙'}
        </button>
      </div>
    </header>
  );
}
