import pandas as pd
import numpy as np
from scipy.stats import poisson

class PoissonModel:
    def __init__(self, df_history: pd.DataFrame):
        """
        Recebe um DataFrame pandas com o histórico de jogos reais.
        O DataFrame deve conter: homeTeamName, awayTeamName, goalsHome, goalsAway
        """
        self.df = df_history.copy()
        
        # Filtra apenas jogos que terminaram e tem placar válido
        self.df = self.df.dropna(subset=['goalsHome', 'goalsAway'])
        self.df['goalsHome'] = pd.to_numeric(self.df['goalsHome'])
        self.df['goalsAway'] = pd.to_numeric(self.df['goalsAway'])

        self._calculate_league_averages()
        self._calculate_team_stats()

    def _calculate_league_averages(self):
        """Calcula a média de gols marcados em casa e fora na liga inteira."""
        total_matches = len(self.df)
        if total_matches == 0:
            self.avg_home_goals = 1.0
            self.avg_away_goals = 1.0
            return
            
        self.avg_home_goals = self.df['goalsHome'].sum() / total_matches
        self.avg_away_goals = self.df['goalsAway'].sum() / total_matches

    def _calculate_team_stats(self):
        """Calcula as Forças de Ataque e Defesa de cada time."""
        # Stats jogando em Casa
        home_stats = self.df.groupby('homeTeamName').agg(
            matches_home=('homeTeamName', 'count'),
            goals_scored_home=('goalsHome', 'sum'),
            goals_conceded_home=('goalsAway', 'sum')
        ).reset_index()

        # Stats jogando Fora
        away_stats = self.df.groupby('awayTeamName').agg(
            matches_away=('awayTeamName', 'count'),
            goals_scored_away=('goalsAway', 'sum'),
            goals_conceded_away=('goalsHome', 'sum')
        ).reset_index()

        # Merge
        stats = pd.merge(home_stats, away_stats, left_on='homeTeamName', right_on='awayTeamName', how='outer').fillna(0)
        stats['Team'] = stats['homeTeamName'].combine_first(stats['awayTeamName'])
        
        # Cálculo de Médias por Jogo do Time
        stats['avg_scored_home'] = stats['goals_scored_home'] / np.where(stats['matches_home'] > 0, stats['matches_home'], 1)
        stats['avg_conceded_home'] = stats['goals_conceded_home'] / np.where(stats['matches_home'] > 0, stats['matches_home'], 1)
        
        stats['avg_scored_away'] = stats['goals_scored_away'] / np.where(stats['matches_away'] > 0, stats['matches_away'], 1)
        stats['avg_conceded_away'] = stats['goals_conceded_away'] / np.where(stats['matches_away'] > 0, stats['matches_away'], 1)

        # Forças de Ataque e Defesa Relativas
        stats['home_attack_strength'] = stats['avg_scored_home'] / self.avg_home_goals
        stats['home_defense_strength'] = stats['avg_conceded_home'] / self.avg_away_goals
        
        stats['away_attack_strength'] = stats['avg_scored_away'] / self.avg_away_goals
        stats['away_defense_strength'] = stats['avg_conceded_away'] / self.avg_home_goals

        self.team_stats = stats.set_index('Team')

    def calculate_xg(self, home_team: str, away_team: str):
        """Calcula os Expected Goals (xG) para uma partida específica."""
        if home_team not in self.team_stats.index or away_team not in self.team_stats.index:
            # Se não tem dados do time, usa a média da liga
            return self.avg_home_goals, self.avg_away_goals

        home_atk = self.team_stats.loc[home_team, 'home_attack_strength']
        away_def = self.team_stats.loc[away_team, 'away_defense_strength']
        
        away_atk = self.team_stats.loc[away_team, 'away_attack_strength']
        home_def = self.team_stats.loc[home_team, 'home_defense_strength']

        home_xg = home_atk * away_def * self.avg_home_goals
        away_xg = away_atk * home_def * self.avg_away_goals

        return home_xg, away_xg

    def predict_match(self, home_team: str, away_team: str, max_goals=6):
        """Gera a Matriz de Poisson e calcula as probabilidades do jogo."""
        home_xg, away_xg = self.calculate_xg(home_team, away_team)
        
        # Cria matriz de probabilidades de placares (0x0 até max_goals x max_goals)
        team_pred = [[poisson.pmf(i, team_avg) for i in range(0, max_goals)] for team_avg in [home_xg, away_xg]]
        
        # Produto externo para matriz bidimensional
        match_matrix = np.outer(np.array(team_pred[0]), np.array(team_pred[1]))
        
        # Calcula as probabilidades 1X2
        home_win_prob = np.sum(np.tril(match_matrix, -1))
        draw_prob = np.sum(np.diag(match_matrix))
        away_win_prob = np.sum(np.triu(match_matrix, 1))

        # Placar Mais Provável
        max_prob_idx = np.unravel_index(np.argmax(match_matrix, axis=None), match_matrix.shape)
        most_likely_score = f"{max_prob_idx[0]} x {max_prob_idx[1]}"
        most_likely_score_prob = match_matrix[max_prob_idx]

        # Probabilidades Over/Under
        # Over 1.5 significa a soma dos índices (gols casa + gols fora) > 1
        over_1_5_prob = 0
        over_2_5_prob = 0
        both_teams_to_score_prob = 0

        for i in range(max_goals):
            for j in range(max_goals):
                total_goals = i + j
                prob = match_matrix[i, j]
                
                if total_goals > 1.5:
                    over_1_5_prob += prob
                if total_goals > 2.5:
                    over_2_5_prob += prob
                if i > 0 and j > 0:
                    both_teams_to_score_prob += prob

        return {
            "Home Win": round(home_win_prob * 100, 2),
            "Draw": round(draw_prob * 100, 2),
            "Away Win": round(away_win_prob * 100, 2),
            "Home xG": round(home_xg, 2),
            "Away xG": round(away_xg, 2),
            "Most Likely Score": most_likely_score,
            "Most Likely Score Prob": round(most_likely_score_prob * 100, 2),
            "Over 1.5": round(over_1_5_prob * 100, 2),
            "Over 2.5": round(over_2_5_prob * 100, 2),
            "BTTS (Ambos Marcam)": round(both_teams_to_score_prob * 100, 2)
        }
