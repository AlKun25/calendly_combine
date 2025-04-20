'use client';

/**
 * Saves data to localStorage.
 * @param key The key under which to store the data.
 * @param data The data to store (will be JSON.stringify'd).
 */
export const saveData = <T>(key: string, data: T): void => {
  if (typeof window !== 'undefined') {
    try {
      const serializedData = JSON.stringify(data);
      window.localStorage.setItem(key, serializedData);
    } catch (error) {
      console.error(`Error saving data to localStorage for key "${key}":`, error);
    }
  }
};

/**
 * Loads data from localStorage.
 * @param key The key of the data to retrieve.
 * @returns The parsed data, or null if not found or an error occurs.
 */
export const loadData = <T>(key: string): T | null => {
  if (typeof window !== 'undefined') {
    try {
      const serializedData = window.localStorage.getItem(key);
      if (serializedData === null) {
        return null;
      }
      return JSON.parse(serializedData) as T;
    } catch (error) {
      console.error(`Error loading data from localStorage for key "${key}":`, error);
      // Optionally remove the invalid item
      // window.localStorage.removeItem(key);
      return null;
    }
  }
  return null; // Return null if not in a browser environment
};

/**
 * Removes data from localStorage.
 * @param key The key of the data to remove.
 */
export const removeData = (key: string): void => {
    if (typeof window !== 'undefined') {
        try {
            window.localStorage.removeItem(key);
        } catch (error) {
            console.error(`Error removing data from localStorage for key "${key}":`, error);
        }
    }
}; 