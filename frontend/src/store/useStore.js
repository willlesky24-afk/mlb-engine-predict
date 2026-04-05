import { create } from 'zustand';

const useStore = create((set) => ({
  // Teams
  teamA: 'NYY',
  teamB: 'LAD',
  setTeamA: (team) => set({ teamA: team }),
  setTeamB: (team) => set({ teamB: team }),

  // Fatigue states
  fatigueA: 20,
  fatigueB: 75,
  setFatigueA: (val) => set({ fatigueA: val }),
  setFatigueB: (val) => set({ fatigueB: val }),

  // Global prediction results from the Python API
  predictionResult: null,
  setPredictionResult: (result) => set({ predictionResult: result }),
}));

export default useStore;
