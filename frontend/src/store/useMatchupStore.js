import { create } from 'zustand';

const useMatchupStore = create((set) => ({
  // Equipos seleccionados
  teamA: 'NYY',
  teamB: 'LAD',
  setTeamA: (team) => set({ teamA: team }),
  setTeamB: (team) => set({ teamB: team }),

  // Jugadores inactivos (arreglo de IDs o nombres)
  inactivePlayersA: [],
  inactivePlayersB: [],
  togglePlayerA: (playerName) => set((state) => ({
    inactivePlayersA: state.inactivePlayersA.includes(playerName)
      ? state.inactivePlayersA.filter(p => p !== playerName)
      : [...state.inactivePlayersA, playerName]
  })),
  togglePlayerB: (playerName) => set((state) => ({
    inactivePlayersB: state.inactivePlayersB.includes(playerName)
      ? state.inactivePlayersB.filter(p => p !== playerName)
      : [...state.inactivePlayersB, playerName]
  })),

  // Pitchers Abridores
  starterA: 'Gerrit Cole (RHP)',
  starterB: 'Yoshinobu Yamamoto (RHP)',
  setStarterA: (pitcher) => set({ starterA: pitcher }),
  setStarterB: (pitcher) => set({ starterB: pitcher }),

  // Metrica de fatiga del bullpen (0-100)
  fatigueA: 20,
  fatigueB: 75,
  setFatigueA: (val) => set({ fatigueA: val }),
  setFatigueB: (val) => set({ fatigueB: val }),
}));

export default useMatchupStore;
