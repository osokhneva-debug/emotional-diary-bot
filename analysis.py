# analysis.py
import json
import csv
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict
import io
import pytz

from db import get_session, User, Entry
from i18n import TEXTS, EMOTION_CATEGORIES

class EmotionAnalyzer:
    """Analyzes emotional data and generates insights"""
    
    def __init__(self):
        # Emotion grouping based on scientific research
        self.emotion_groups = {
            'recovery_growth': {
                'name': '🌱 Эмоции восстановления и роста',
                'categories': ['Радость/Удовлетворение', 'Интерес/Любопытство', 'Спокойствие/Умиротворение', 'Энергичность/Воодушевление'],
                'description': 'Эмоции, способствующие развитию и восстановлению'
            },
            'tension_signal': {
                'name': '🌪 Эмоции напряжения и сигнала',
                'categories': ['Тревога/Беспокойство', 'Грусть/Печаль', 'Злость/Раздражение', 'Стыд/Вина', 'Усталость/Истощение', 'Удивление/Шок'],
                'description': 'Эмоции, сигнализирующие о потребностях и вызовах'
            },
            'neutral': {
                'name': '⚖ Нейтральные состояния',
                'categories': [],
                'description': 'Сбалансированные и нейтральные состояния'
            }
        }
    
    async def generate_summary(self, user_id: int, period: str) -> str:
        """Generate emotional summary for specified period"""
        try:
            # Parse period
            days = self._parse_period(period)
            if not days:
                return TEXTS['invalid_period']
            
            # Get entries for the period
            entries = self._get_entries_for_period(user_id, days)
            
            if not entries:
                return TEXTS['no_data_for_period'].format(period=days)
            
            # Generate comprehensive analysis
            summary_parts = []
            
            # Header
            summary_parts.append(f"📊 <b>Анализ за {days} дней</b>")
            summary_parts.append(f"📅 Записей: {len(entries)}")
            summary_parts.append("")
            
            # Emotion groups analysis
            group_analysis = self._analyze_emotion_groups(entries)
            summary_parts.append("🎭 <b>Анализ эмоциональных групп:</b>")
            
            for group_key, group_data in self.emotion_groups.items():
                count = group_analysis.get(group_key, 0)
                percentage = (count / len(entries) * 100) if entries else 0
                summary_parts.append(f"{group_data['name']}: {count} ({percentage:.1f}%)")
            
            summary_parts.append("")
            
            # Most frequent emotions
            emotion_freq = self._get_emotion_frequency(entries)
            if emotion_freq:
                summary_parts.append("🏆 <b>Частые эмоции:</b>")
                for emotion, count in emotion_freq.most_common(5):
                    summary_parts.append(f"• {emotion}: {count} раз")
                summary_parts.append("")
            
            # Trigger analysis
            trigger_analysis = self._analyze_triggers(entries)
            if trigger_analysis:
                summary_parts.append("🎯 <b>Основные триггеры:</b>")
                for trigger, emotions in list(trigger_analysis.items())[:3]:
                    emotions_str = ", ".join(emotions[:3])
                    summary_parts.append(f"• {trigger}: {emotions_str}")
                summary_parts.append("")
            
            # Time patterns
            time_patterns = self._analyze_time_patterns(entries)
            if time_patterns:
                summary_parts.append("⏰ <b>Временные паттерны:</b>")
                peak_hour = max(time_patterns.items(), key=lambda x: x[1])
                summary_parts.append(f"• Пик активности: {peak_hour[0]}:00 ({peak_hour[1]} записей)")
                summary_parts.append("")
            
            # Personalized insights for working women
            insights = self._generate_personalized_insights(entries, group_analysis)
            if insights:
                summary_parts.append("💡 <b>Персональные инсайты:</b>")
                for insight in insights:
                    summary_parts.append(f"• {insight}")
                summary_parts.append("")
            
            # Valence and arousal trends
            valence_avg = sum(e.valence for e in entries) / len(entries)
            arousal_avg = sum(e.arousal for e in entries) / len(entries)
            
            summary_parts.append("📈 <b>Общие тенденции:</b>")
            summary_parts.append(f"• Средняя валентность: {self._format_valence(valence_avg)}")
            summary_parts.append(f"• Средняя активация: {self._format_arousal(arousal_avg)}")
            
            # Footer with scientific note
            summary_parts.append("")
            summary_parts.append("🔬 <i>Отслеживание эмоций помогает развивать эмоциональную осознанность и улучшать саморегуляцию.</i>")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            return f"Ошибка при генерации сводки: {str(e)}"
    
    def _parse_period(self, period: str) -> Optional[int]:
        """Parse period string to number of days"""
        period_map = {
            "7": 7,
            "14": 14,
            "30": 30,
            "90": 90
        }
        return period_map.get(period)
    
    def _get_entries_for_period(self, user_id: int, days: int) -> List[Entry]:
        """Get entries for the specified period"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        with get_session() as session:
            return session.query(Entry).filter(
                Entry.user_id == user_id,
                Entry.timestamp >= cutoff_date
            ).order_by(Entry.timestamp.desc()).all()
    
    def _analyze_emotion_groups(self, entries: List[Entry]) -> Dict[str, int]:
        """Analyze emotion distribution by groups"""
        group_counts = defaultdict(int)
        
        for entry in entries:
            category = entry.category
            
            # Find which group this category belongs to
            group_found = False
            for group_key, group_data in self.emotion_groups.items():
                if category in group_data['categories']:
                    group_counts[group_key] += 1
                    group_found = True
                    break
            
            # If not found in specific groups, count as neutral
            if not group_found:
                group_counts['neutral'] += 1
        
        return dict(group_counts)
    
    def _get_emotion_frequency(self, entries: List[Entry]) -> Counter:
        """Get frequency of specific emotions"""
        emotion_counts = Counter()
        
        for entry in entries:
            if entry.emotions:
                emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
                for emotion in emotions:
                    emotion_counts[emotion] += 1
        
        return emotion_counts
    
    def _analyze_triggers(self, entries: List[Entry]) -> Dict[str, List[str]]:
        """Analyze what triggers different emotions"""
        trigger_emotions = defaultdict(set)
        
        for entry in entries:
            if entry.cause and entry.emotions:
                cause = entry.cause.strip()
                if len(cause) > 3:  # Filter out very short causes
                    emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
                    for emotion in emotions:
                        trigger_emotions[cause].add(emotion)
        
        # Convert sets to lists and filter by frequency
        result = {}
        for trigger, emotions in trigger_emotions.items():
            if len(emotions) >= 1:  # At least 1 emotion
                result[trigger] = list(emotions)
        
        return result
    
    def _analyze_time_patterns(self, entries: List[Entry]) -> Dict[int, int]:
        """Analyze emotional activity by hour of day"""
        hour_counts = defaultdict(int)
        
        for entry in entries:
            hour = entry.timestamp.hour
            hour_counts[hour] += 1
        
        return dict(hour_counts)
    
    def _generate_personalized_insights(self, entries: List[Entry], group_analysis: Dict[str, int]) -> List[str]:
        """Generate personalized insights for working women"""
        insights = []
        total_entries = len(entries)
        
        if total_entries == 0:
            return insights
        
        # Analyze work-life balance patterns
        work_related_emotions = self._count_work_related_emotions(entries)
        evening_stress = self._count_evening_stress(entries)
        morning_anxiety = self._count_morning_anxiety(entries)
        
        # Insight about morning anxiety
        if morning_anxiety > total_entries * 0.3:
            insights.append("Замечена тревожность по утрам - попробуйте дыхательные практики перед началом дня")
        
        # Insight about evening stress
        if evening_stress > total_entries * 0.25:
            insights.append("Вечерний стресс может говорить о необходимости лучших границ между работой и личной жизнью")
        
        # Insight about emotion balance
        tension_ratio = group_analysis.get('tension_signal', 0) / total_entries
        if tension_ratio > 0.7:
            insights.append("Высокий уровень напряженных эмоций - важно уделить время восстановлению")
        elif tension_ratio < 0.3:
            insights.append("Хороший баланс эмоций - продолжайте поддерживать практики самозаботы")
        
        # Insight about emotional variety
        unique_emotions = len(self._get_unique_emotions(entries))
        if unique_emotions < 5:
            insights.append("Попробуйте расширить эмоциональный словарь - это поможет лучше понимать свои состояния")
        
        # Work-related stress insights
        if work_related_emotions > total_entries * 0.4:
            insights.append("Много рабочих переживаний - подумайте о техниках переключения после работы")
        
        return insights[:3]  # Return max 3 insights
    
    def _count_work_related_emotions(self, entries: List[Entry]) -> int:
        """Count emotions related to work"""
        work_keywords = ['работ', 'коллег', 'босс', 'проект', 'дедлайн', 'совещ', 'офис', 'клиент']
        count = 0
        
        for entry in entries:
            if entry.cause:
                cause_lower = entry.cause.lower()
                if any(keyword in cause_lower for keyword in work_keywords):
                    count += 1
        
        return count
    
    def _count_evening_stress(self, entries: List[Entry]) -> int:
        """Count stressful emotions in evening hours (18-23)"""
        stress_emotions = ['тревога', 'беспокойство', 'усталость', 'истощение', 'раздражение', 'фрустрация']
        count = 0
        
        for entry in entries:
            if 18 <= entry.timestamp.hour <= 23:
                if entry.emotions:
                    emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
                    if any(emotion.lower() in stress_emotions for emotion in emotions):
                        count += 1
        
        return count
    
    def _count_morning_anxiety(self, entries: List[Entry]) -> int:
        """Count anxiety-related emotions in morning hours (6-11)"""
        anxiety_emotions = ['тревога', 'беспокойство', 'нервозность', 'напряжение', 'сомнение']
        count = 0
        
        for entry in entries:
            if 6 <= entry.timestamp.hour <= 11:
                if entry.emotions:
                    emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
                    if any(emotion.lower() in anxiety_emotions for emotion in emotions):
                        count += 1
        
        return count
    
    def _get_unique_emotions(self, entries: List[Entry]) -> set:
        """Get set of unique emotions from entries"""
        unique_emotions = set()
        
        for entry in entries:
            if entry.emotions:
                emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
                unique_emotions.update(emotions)
        
        return unique_emotions
    
    def _format_valence(self, valence: float) -> str:
        """Format valence value to human-readable string"""
        if valence > 0.3:
            return "Позитивная 😊"
        elif valence < -0.3:
            return "Негативная 😔"
        else:
            return "Нейтральная 😐"
    
    def _format_arousal(self, arousal: float) -> str:
        """Format arousal value to human-readable string"""
        if arousal > 1.3:
            return "Высокая энергия ⚡"
        elif arousal > 0.7:
            return "Средняя энергия 🌊"
        else:
            return "Низкая энергия 😴"
    
    def generate_csv_export(self, entries: List[Entry]) -> io.BytesIO:
        """Generate CSV export of emotional data"""
        output = io.StringIO()
        
        fieldnames = [
            'Дата', 'Время', 'Валентность', 'Активация', 'Категория',
            'Эмоции', 'Причина', 'Телесные_ощущения', 'Заметки', 'Теги'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for entry in entries:
            emotions_str = ', '.join(json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions) if entry.emotions else ''
            tags_str = ', '.join(json.loads(entry.tags) if isinstance(entry.tags, str) else entry.tags) if entry.tags else ''
            
            writer.writerow({
                'Дата': entry.timestamp.strftime('%Y-%m-%d'),
                'Время': entry.timestamp.strftime('%H:%M:%S'),
                'Валентность': entry.valence,
                'Активация': entry.arousal,
                'Категория': entry.category or '',
                'Эмоции': emotions_str,
                'Причина': entry.cause or '',
                'Телесные_ощущения': entry.body_sensations or '',
                'Заметки': entry.notes or '',
                'Теги': tags_str
            })
        
        # Convert to bytes
        output.seek(0)
        csv_bytes = io.BytesIO()
        csv_bytes.write(output.getvalue().encode('utf-8-sig'))  # UTF-8 with BOM for Excel
        csv_bytes.seek(0)
        
        return csv_bytes
    
    def get_emotion_trends(self, user_id: int, days: int = 30) -> Dict:
        """Get emotion trends over time"""
        entries = self._get_entries_for_period(user_id, days)
        
        if not entries:
            return {}
        
        # Group by day
        daily_data = defaultdict(lambda: {'valence': [], 'arousal': [], 'count': 0})
        
        for entry in entries:
            day_key = entry.timestamp.strftime('%Y-%m-%d')
            daily_data[day_key]['valence'].append(entry.valence)
            daily_data[day_key]['arousal'].append(entry.arousal)
            daily_data[day_key]['count'] += 1
        
        # Calculate daily averages
        trends = {}
        for day, data in daily_data.items():
            trends[day] = {
                'avg_valence': sum(data['valence']) / len(data['valence']),
                'avg_arousal': sum(data['arousal']) / len(data['arousal']),
                'entry_count': data['count']
            }
        
        return trends
    
    def get_weekly_comparison(self, user_id: int) -> Dict:
        """Compare this week with previous week"""
        now = datetime.now(timezone.utc)
        
        # Current week (last 7 days)
        current_week_entries = self._get_entries_for_period(user_id, 7)
        
        # Previous week (8-14 days ago)
        prev_week_start = now - timedelta(days=14)
        prev_week_end = now - timedelta(days=7)
        
        with get_session() as session:
            prev_week_entries = session.query(Entry).filter(
                Entry.user_id == user_id,
                Entry.timestamp >= prev_week_start,
                Entry.timestamp < prev_week_end
            ).all()
        
        def analyze_week(entries):
            if not entries:
                return {'valence': 0, 'arousal': 0, 'count': 0, 'top_emotions': []}
            
            valence_avg = sum(e.valence for e in entries) / len(entries)
            arousal_avg = sum(e.arousal for e in entries) / len(entries)
            
            emotion_freq = self._get_emotion_frequency(entries)
            top_emotions = [emotion for emotion, count in emotion_freq.most_common(3)]
            
            return {
                'valence': valence_avg,
                'arousal': arousal_avg,
                'count': len(entries),
                'top_emotions': top_emotions
            }
        
        current_analysis = analyze_week(current_week_entries)
        previous_analysis = analyze_week(prev_week_entries)
        
        # Calculate changes
        valence_change = current_analysis['valence'] - previous_analysis['valence']
        arousal_change = current_analysis['arousal'] - previous_analysis['arousal']
        
        return {
            'current_week': current_analysis,
            'previous_week': previous_analysis,
            'changes': {
                'valence': valence_change,
                'arousal': arousal_change,
                'entries': current_analysis['count'] - previous_analysis['count']
            }
        }
    
    def get_emotion_correlations(self, user_id: int, days: int = 30) -> Dict:
        """Find correlations between emotions and times/triggers"""
        entries = self._get_entries_for_period(user_id, days)
        
        if not entries:
            return {}
        
        # Time-emotion correlations
        time_emotions = defaultdict(list)
        for entry in entries:
            hour = entry.timestamp.hour
            if entry.emotions:
                emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
                time_emotions[hour].extend(emotions)
        
        # Find most common emotions by time of day
        time_correlations = {}
        for hour, emotions in time_emotions.items():
            emotion_counts = Counter(emotions)
            if emotion_counts:
                most_common = emotion_counts.most_common(1)[0]
                time_correlations[hour] = {
                    'emotion': most_common[0],
                    'frequency': most_common[1],
                    'total_entries': len(emotions)
                }
        
        # Trigger-emotion patterns
        trigger_patterns = defaultdict(list)
        for entry in entries:
            if entry.cause and entry.emotions:
                cause_words = entry.cause.lower().split()
                emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
                
                for word in cause_words:
                    if len(word) > 3:  # Filter short words
                        trigger_patterns[word].extend(emotions)
        
        # Find strongest trigger-emotion associations
        trigger_correlations = {}
        for trigger, emotions in trigger_patterns.items():
            if len(emotions) >= 2:  # At least 2 occurrences
                emotion_counts = Counter(emotions)
                most_common = emotion_counts.most_common(1)[0]
                trigger_correlations[trigger] = {
                    'emotion': most_common[0],
                    'frequency': most_common[1],
                    'total_entries': len(emotions)
                }
        
        return {
            'time_correlations': time_correlations,
            'trigger_correlations': dict(list(trigger_correlations.items())[:10])  # Top 10
        }
