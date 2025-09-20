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
        # Исправленная группировка эмоций на основе научных исследований
        self.emotion_groups = {
            'recovery_growth': {
                'name': '🌱 Эмоции восстановления и роста',
                'keywords': [
                    # Радость/Удовлетворение
                    'радость', 'счастье', 'восторг', 'благодарность', 'вдохновение', 'гордость', 'удовлетворение', 'блаженство',
                    # Интерес/Любопытство  
                    'интерес', 'любопытство', 'увлечённость', 'предвкушение', 'азарт', 'заинтересованность', 'любознательность',
                    # Спокойствие/Умиротворение
                    'спокойствие', 'расслабленность', 'гармония', 'принятие', 'безопасность', 'умиротворение', 'безмятежность', 'равновесие',
                    # Энергичность/Воодушевление
                    'бодрость', 'энтузиазм', 'возбуждение', 'решимость', 'драйв', 'воодушевление', 'подъём', 'энергия'
                ],
                'description': 'Эмоции, способствующие развитию и восстановлению'
            },
            'tension_signal': {
                'name': '🌪 Эмоции напряжения и сигнала',
                'keywords': [
                    # Тревога/Беспокойство
                    'тревога', 'беспокойство', 'нервозность', 'страх', 'напряжение', 'сомнение', 'волнение', 'опасение',
                    # Грусть/Печаль
                    'грусть', 'печаль', 'тоска', 'разочарование', 'меланхолия', 'одиночество', 'горе', 'уныние', 'сожаление',
                    # Злость/Раздражение
                    'злость', 'раздражение', 'гнев', 'обида', 'фрустрация', 'зависть', 'возмущение', 'негодование',
                    # Стыд/Вина
                    'стыд', 'вина', 'смущение', 'неловкость', 'самокритика', 'угрызения', 'раскаяние',
                    # Усталость/Истощение
                    'усталость', 'истощение', 'апатия', 'выгорание', 'безразличие', 'вялость', 'изнеможение', 'опустошённость',
                    # Удивление/Шок
                    'удивление', 'изумление', 'ошеломление', 'растерянность', 'недоумение', 'потрясение', 'шок'
                ],
                'description': 'Эмоции, сигнализирующие о потребностях и вызовах'
            },
            'neutral': {
                'name': '⚖ Нейтральные/прочие состояния',
                'keywords': [
                    'нейтрально', 'обычно', 'нормально', 'неопределенность', 'неясность', 'смешанность'
                ],
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
                return f"📭 За последние {days} дней нет записей эмоций.\n\nНачни отслеживать свои эмоции с помощью /note!"
            
            # Generate comprehensive analysis
            summary_parts = []
            
            # Header
            period_name = {7: "неделю", 14: "2 недели", 30: "месяц", 90: "3 месяца"}.get(days, f"{days} дней")
            summary_parts.append(f"📊 <b>Сводка за {period_name}</b>")
            summary_parts.append("")
            summary_parts.append("📊 <b>Твоя неделя в эмоциях</b>")
            summary_parts.append("")
            
            # Emotion groups analysis
            group_analysis = self._analyze_emotion_groups(entries)
            emotion_details = self._get_emotion_details_by_group(entries)
            
            summary_parts.append("<b>🎭 Эмоции по группам:</b>")
            summary_parts.append("")
            
            for group_key, group_data in self.emotion_groups.items():
                count = group_analysis.get(group_key, 0)
                group_name = group_data['name']
                
                summary_parts.append(f"<b>{group_name}:</b> {count} раз")
                
                # Добавляем детали эмоций для каждой группы
                if count > 0 and group_key in emotion_details:
                    emotions_list = []
                    for emotion, freq in emotion_details[group_key].most_common(5):
                        emotions_list.append(f'"{emotion}" ({freq})')
                    if emotions_list:
                        summary_parts.append(", ".join(emotions_list))
                
                summary_parts.append("")
            
            # Trigger analysis by groups
            trigger_analysis = self._analyze_triggers_by_groups(entries)
            if trigger_analysis:
                summary_parts.append("<b>🔍 Что влияло на эмоции:</b>")
                summary_parts.append("")
                
                for group_key, triggers in trigger_analysis.items():
                    if triggers:
                        group_name = self.emotion_groups[group_key]['name']
                        # Сокращаем название для триггеров
                        if 'восстановления и роста' in group_name:
                            trigger_title = "🌱 Триггеры позитивных эмоций:"
                        elif 'напряжения и сигнала' in group_name:
                            trigger_title = "🌪 Триггеры напряженных эмоций:"
                        else:
                            trigger_title = "⚖ Триггеры нейтральных эмоций:"
                        
                        summary_parts.append(f"<b>{trigger_title}</b>")
                        for trigger in triggers[:3]:  # Показываем только топ-3
                            summary_parts.append(f"• {trigger}")
                        summary_parts.append("")
            
            # Time patterns
            time_patterns = self._analyze_time_patterns(entries)
            if time_patterns:
                peak_hour = max(time_patterns.items(), key=lambda x: x[1])
                time_of_day = self._get_time_of_day_name(peak_hour[0])
                summary_parts.append(f"<b>⏰ Пик активности:</b> {peak_hour[0]}:00 ({time_of_day})")
            
            summary_parts.append(f"<b>📈 Всего записей:</b> {len(entries)}")
            summary_parts.append("")
            
            # Footer
            summary_parts.append("<i>Хочешь подробности? Используй /export для CSV-файла.</i>")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            return f"Ошибка при генерации сводки: {str(e)}"
    
    def _analyze_emotion_groups(self, entries: List[Entry]) -> Dict[str, int]:
        """Analyze emotion distribution by groups using keyword matching"""
        group_counts = defaultdict(int)
        
        for entry in entries:
            if not entry.emotions:
                continue
                
            emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
            
            for emotion in emotions:
                emotion_lower = emotion.lower().strip()
                group_found = False
                
                # Проверяем каждую группу
                for group_key, group_data in self.emotion_groups.items():
                    keywords = group_data['keywords']
                    
                    # Ищем точное совпадение или частичное вхождение
                    for keyword in keywords:
                        if (emotion_lower == keyword.lower() or 
                            keyword.lower() in emotion_lower or 
                            emotion_lower in keyword.lower()):
                            group_counts[group_key] += 1
                            group_found = True
                            break
                    
                    if group_found:
                        break
                
                # Если эмоция не найдена ни в одной группе, относим к нейтральным
                if not group_found:
                    group_counts['neutral'] += 1
        
        return dict(group_counts)
    
    def _get_emotion_details_by_group(self, entries: List[Entry]) -> Dict[str, Counter]:
        """Get detailed emotion counts for each group"""
        group_emotions = defaultdict(Counter)
        
        for entry in entries:
            if not entry.emotions:
                continue
                
            emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
            
            for emotion in emotions:
                emotion_lower = emotion.lower().strip()
                group_found = False
                
                # Проверяем каждую группу
                for group_key, group_data in self.emotion_groups.items():
                    keywords = group_data['keywords']
                    
                    # Ищем точное совпадение или частичное вхождение
                    for keyword in keywords:
                        if (emotion_lower == keyword.lower() or 
                            keyword.lower() in emotion_lower or 
                            emotion_lower in keyword.lower()):
                            group_emotions[group_key][emotion] += 1
                            group_found = True
                            break
                    
                    if group_found:
                        break
                
                # Если эмоция не найдена ни в одной группе, относим к нейтральным
                if not group_found:
                    group_emotions['neutral'][emotion] += 1
        
        return dict(group_emotions)
    
    def _analyze_triggers_by_groups(self, entries: List[Entry]) -> Dict[str, List[str]]:
        """Analyze triggers grouped by emotion groups"""
        group_triggers = defaultdict(list)
        
        for entry in entries:
            if not entry.cause or not entry.emotions:
                continue
                
            emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
            cause = entry.cause.strip()
            
            if len(cause) < 3:  # Игнорируем очень короткие причины
                continue
            
            # Определяем к какой группе относится эта запись
            emotion_group = None
            for emotion in emotions:
                emotion_lower = emotion.lower().strip()
                
                for group_key, group_data in self.emotion_groups.items():
                    keywords = group_data['keywords']
                    
                    for keyword in keywords:
                        if (emotion_lower == keyword.lower() or 
                            keyword.lower() in emotion_lower or 
                            emotion_lower in keyword.lower()):
                            emotion_group = group_key
                            break
                    
                    if emotion_group:
                        break
                
                if emotion_group:
                    break
            
            # Если группа не определена, относим к нейтральным
            if not emotion_group:
                emotion_group = 'neutral'
            
            group_triggers[emotion_group].append(cause)
        
        return dict(group_triggers)
    
    def _get_time_of_day_name(self, hour: int) -> str:
        """Get human-readable time of day name"""
        if 6 <= hour < 12:
            return "утром"
        elif 12 <= hour < 17:
            return "днём"
        elif 17 <= hour < 22:
            return "вечером"
        else:
            return "ночью"
    
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
    
    def _get_emotion_frequency(self, entries: List[Entry]) -> Counter:
        """Get frequency of specific emotions"""
        emotion_counts = Counter()
        
        for entry in entries:
            if entry.emotions:
                emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
                for emotion in emotions:
                    emotion_counts[emotion] += 1
        
        return emotion_counts
    
    def _analyze_time_patterns(self, entries: List[Entry]) -> Dict[int, int]:
        """Analyze emotional activity by hour of day"""
        hour_counts = defaultdict(int)
        
        for entry in entries:
            hour = entry.timestamp.hour
            hour_counts[hour] += 1
        
        return dict(hour_counts)
    
    def generate_csv_export(self, entries: List[Entry]) -> io.BytesIO:
        """Generate CSV export of emotional data"""
        output = io.StringIO()
        
        fieldnames = [
            'Дата', 'Время', 'Эмоции', 'Группа_эмоций', 'Причина', 'Заметки'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for entry in entries:
            emotions_str = ', '.join(json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions) if entry.emotions else ''
            
            # Определяем группу эмоций для CSV
            emotion_group = "Нейтральные"
            if entry.emotions:
                emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
                for emotion in emotions:
                    emotion_lower = emotion.lower().strip()
                    
                    for group_key, group_data in self.emotion_groups.items():
                        keywords = group_data['keywords']
                        
                        for keyword in keywords:
                            if (emotion_lower == keyword.lower() or 
                                keyword.lower() in emotion_lower or 
                                emotion_lower in keyword.lower()):
                                if group_key == 'recovery_growth':
                                    emotion_group = "Восстановления и роста"
                                elif group_key == 'tension_signal':
                                    emotion_group = "Напряжения и сигнала"
                                else:
                                    emotion_group = "Нейтральные"
                                break
                        
                        if emotion_group != "Нейтральные":
                            break
                    
                    if emotion_group != "Нейтральные":
                        break
            
            writer.writerow({
                'Дата': entry.timestamp.strftime('%Y-%m-%d'),
                'Время': entry.timestamp.strftime('%H:%M:%S'),
                'Эмоции': emotions_str,
                'Группа_эмоций': emotion_group,
                'Причина': entry.cause or '',
                'Заметки': entry.notes or ''
            })
        
        # Convert to bytes
        output.seek(0)
        csv_bytes = io.BytesIO()
        csv_bytes.write(output.getvalue().encode('utf-8-sig'))  # UTF-8 with BOM for Excel
        csv_bytes.seek(0)
        
        return csv_bytes
