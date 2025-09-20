# analysis.py
import json
import csv
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from collections import Counter, defaultdict
import io
import logging

from db import get_session, User, Entry
from i18n import TEXTS, EMOTION_CATEGORIES

logger = logging.getLogger(__name__)

class EmotionAnalyzer:
    """Analyzes emotional data and generates insights"""
    
    def __init__(self):
        # Группировка эмоций на основе научных исследований
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
                return TEXTS.get('invalid_period', 'Неверный период для анализа.')
            
            # Get entries for the period
            entries = self._get_entries_for_period(user_id, days)
            
            if not entries:
                period_name = {7: "неделю", 14: "2 недели", 30: "месяц", 90: "3 месяца"}.get(days, f"{days} дней")
                return f"📭 За последние {days} дней нет записей эмоций.\n\nНачните отслеживать свои эмоции с помощью /note!"
            
            # Generate comprehensive analysis
            summary_parts = []
            
            # Header
            period_name = {7: "неделю", 14: "2 недели", 30: "месяц", 90: "3 месяца"}.get(days, f"{days} дней")
            summary_parts.append(f"📊 <b>Сводка за {period_name}</b>")
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
                        # Экранируем HTML символы в названиях эмоций
                        emotion_escaped = self._escape_html(emotion)
                        emotions_list.append(f'"{emotion_escaped}" ({freq})')
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
                            trigger_escaped = self._escape_html(trigger)
                            summary_parts.append(f"• {trigger_escaped}")
                        summary_parts.append("")
            
            # Time patterns
            time_patterns = self._analyze_time_patterns(entries)
            if time_patterns:
                peak_hour = max(time_patterns.items(), key=lambda x: x[1])
                time_of_day = self._get_time_of_day_name(peak_hour[0])
                summary_parts.append(f"<b>⏰ Пик активности:</b> {peak_hour[0]}:00 ({time_of_day})")
            
            summary_parts.append(f"<b>📈 Всего записей:</b> {len(entries)}")
            summary_parts.append("")
            
            # Add insights for working women
            insights = self._generate_insights_for_working_women(entries, group_analysis)
            if insights:
                summary_parts.append("<b>💡 Персональные инсайты:</b>")
                for insight in insights:
                    summary_parts.append(f"• {insight}")
                summary_parts.append("")
            
            # Footer
            summary_parts.append("<i>Хочешь подробности? Используй /export для CSV-файла.</i>")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error generating summary for user {user_id}: {e}")
            return "Ошибка при генерации сводки. Попробуйте позже."
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML characters in text"""
        if not text:
            return ""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    def _analyze_emotion_groups(self, entries: List[Entry]) -> Dict[str, int]:
        """Analyze emotion distribution by groups using keyword matching"""
        group_counts = defaultdict(int)
        
        for entry in entries:
            if not entry.emotions:
                continue
                
            try:
                emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
            except (json.JSONDecodeError, TypeError):
                continue
            
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
                
            try:
                emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
            except (json.JSONDecodeError, TypeError):
                continue
            
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
        group_triggers = defaultdict(Counter)
        
        for entry in entries:
            if not entry.cause or not entry.emotions:
                continue
                
            try:
                emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
            except (json.JSONDecodeError, TypeError):
                continue
                
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
            
            group_triggers[emotion_group][cause] += 1
        
        # Конвертируем в списки топ триггеров для каждой группы
        result = {}
        for group, triggers_counter in group_triggers.items():
            result[group] = [trigger for trigger, _ in triggers_counter.most_common(5)]
        
        return result
    
    def _generate_insights_for_working_women(self, entries: List[Entry], group_analysis: Dict[str, int]) -> List[str]:
        """Generate personalized insights for working women"""
        insights = []
        
        total_entries = len(entries)
        if total_entries == 0:
            return insights
        
        # Анализ баланса эмоций
        positive_count = group_analysis.get('recovery_growth', 0)
        negative_count = group_analysis.get('tension_signal', 0)
        
        positive_ratio = positive_count / total_entries if total_entries > 0 else 0
        negative_ratio = negative_count / total_entries if total_entries > 0 else 0
        
        # Инсайты на основе баланса эмоций
        if negative_ratio > 0.7:
            insights.append("Высокий уровень напряженных эмоций. Рассмотрите техники стрессменеджмента.")
        elif positive_ratio > 0.6:
            insights.append("Отличный эмоциональный баланс! Продолжайте заботиться о себе.")
        elif negative_ratio > positive_ratio:
            insights.append("Больше сигнальных эмоций. Возможно, стоит пересмотреть нагрузку.")
        
        # Анализ временных паттернов
        time_patterns = self._analyze_time_patterns(entries)
        if time_patterns:
            morning_entries = sum(count for hour, count in time_patterns.items() if 6 <= hour <= 12)
            evening_entries = sum(count for hour, count in time_patterns.items() if 18 <= hour <= 23)
            
            if evening_entries > morning_entries * 1.5:
                insights.append("Больше записей вечером. Создайте ритуал завершения рабочего дня.")
        
        # Анализ разнообразия эмоций
        unique_emotions = set()
        for entry in entries:
            if entry.emotions:
                try:
                    emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
                    unique_emotions.update(emotions)
                except (json.JSONDecodeError, TypeError):
                    continue
        
        emotion_variety = len(unique_emotions)
        if emotion_variety < 5 and total_entries > 10:
            insights.append("Попробуйте расширить эмоциональный словарь для лучшего самопонимания.")
        elif emotion_variety > 15:
            insights.append("Богатый эмоциональный словарь помогает вам лучше понимать себя!")
        
        return insights[:3]  # Максимум 3 инсайта
    
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
        
        try:
            with get_session() as session:
                return session.query(Entry).filter(
                    Entry.user_id == user_id,
                    Entry.timestamp >= cutoff_date
                ).order_by(Entry.timestamp.desc()).all()
        except Exception as e:
            logger.error(f"Error getting entries for user {user_id}: {e}")
            return []
    
    def _analyze_time_patterns(self, entries: List[Entry]) -> Dict[int, int]:
        """Analyze emotional activity by hour of day"""
        hour_counts = defaultdict(int)
        
        for entry in entries:
            if entry.timestamp:
                hour = entry.timestamp.hour
                hour_counts[hour] += 1
        
        return dict(hour_counts)
    
    def generate_csv_export(self, entries: List[Entry]) -> io.BytesIO:
        """Generate CSV export of emotional data"""
        output = io.StringIO()
        
        fieldnames = [
            'Дата', 'Время', 'Эмоции', 'Группа_эмоций', 'Причина', 'Заметки', 'Валентность', 'Активация'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for entry in entries:
            try:
                emotions_str = ''
                emotion_group = "Нейтральные"
                
                if entry.emotions:
                    emotions = json.loads(entry.emotions) if isinstance(entry.emotions, str) else entry.emotions
                    emotions_str = ', '.join(emotions)
                    
                    # Определяем группу эмоций для CSV
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
                
                # Конвертируем валентность и активацию в текст
                valence_text = ""
                if entry.valence is not None:
                    if entry.valence > 0.3:
                        valence_text = "Положительная"
                    elif entry.valence < -0.3:
                        valence_text = "Отрицательная"
                    else:
                        valence_text = "Нейтральная"
                
                arousal_text = ""
                if entry.arousal is not None:
                    if entry.arousal > 1.3:
                        arousal_text = "Высокая"
                    elif entry.arousal < 0.7:
                        arousal_text = "Низкая"
                    else:
                        arousal_text = "Средняя"
                
                writer.writerow({
                    'Дата': entry.timestamp.strftime('%Y-%m-%d') if entry.timestamp else '',
                    'Время': entry.timestamp.strftime('%H:%M:%S') if entry.timestamp else '',
                    'Эмоции': emotions_str,
                    'Группа_эмоций': emotion_group,
                    'Причина': entry.cause or '',
                    'Заметки': entry.notes or '',
                    'Валентность': valence_text,
                    'Активация': arousal_text
                })
            except Exception as e:
                logger.error(f"Error processing entry {entry.id}: {e}")
                continue
        
        # Convert to bytes
        output.seek(0)
        csv_bytes = io.BytesIO()
        csv_bytes.write(output.getvalue().encode('utf-8-sig'))  # UTF-8 with BOM for Excel
        csv_bytes.seek(0)
        
        return csv_bytes
