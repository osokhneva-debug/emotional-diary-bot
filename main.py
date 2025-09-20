2025-09-20 21:45:46,623 - aiohttp.access - INFO - 127.0.0.1 [20/Sep/2025:21:45:46 +0300] "GET / HTTP/1.1" 200 188 "-" "Go-http-client/2.0"
2025-09-20 21:46:49,943 - telegram.ext.Application - ERROR - No error handlers are registered, logging exception.
Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/telegram/ext/_application.py", line 1234, in process_update
    await coroutine
  File "/usr/local/lib/python3.11/site-packages/telegram/ext/_basehandler.py", line 157, in handle_update
    return await self.callback(update, context)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: rate_limit.<locals>.decorator() takes 1 positional argument but 3 were given
2025-09-20 21:46:49,946 - aiohttp.access - INFO - 127.0.0.1 [20/Sep/2025:21:46:49 +0300] "POST /webhook HTTP/1.1" 200 153 "-" "-"
     ==> Deploying...
2025-09-20 21:47:47,035 - __main__ - INFO - Bot token loaded: 8028767407:AAH4dBzc8...6tY2oXHYd0
2025-09-20 21:47:47,036 - __main__ - INFO - Webhook URL: https://emojournal1.onrender.com
2025-09-20 21:47:47,036 - __main__ - INFO - Port: 8080
2025-09-20 21:47:47,736 - __main__ - INFO - Starting bot setup...
2025-09-20 21:47:48,030 - httpx - INFO - HTTP Request: POST https://api.telegram.org/bot8028767407:AAH4dBzc8dgYPY25_yuztggbG6tY2oXHYd0/getMe "HTTP/1.1 200 OK"
2025-09-20 21:47:48,031 - __main__ - INFO - Application initialized successfully
2025-09-20 21:47:48,117 - db - INFO - Database initialized successfully
2025-09-20 21:47:48,117 - apscheduler.scheduler - INFO - Scheduler started
2025-09-20 21:47:48,143 - scheduler - INFO - Scheduled daily pings for 0 active users
2025-09-20 21:47:48,143 - scheduler - INFO - Scheduled weekly summaries for 0 active users
2025-09-20 21:47:48,144 - apscheduler.scheduler - INFO - Added job "EmotionScheduler.cleanup_old_data" to job store "default"
2025-09-20 21:47:48,144 - apscheduler.scheduler - INFO - Added job "EmotionScheduler.reschedule_all_users" to job store "default"
2025-09-20 21:47:48,144 - scheduler - INFO - Scheduled maintenance tasks
2025-09-20 21:47:48,144 - scheduler - INFO - Emotion scheduler started successfully
2025-09-20 21:47:48,144 - __main__ - INFO - Bot setup completed
2025-09-20 21:47:48,144 - __main__ - INFO - Bot setup completed
2025-09-20 21:47:48,145 - __main__ - INFO - Setting up web server...
2025-09-20 21:47:48,231 - __main__ - INFO - Web server started on port 8080
2025-09-20 21:47:48,231 - __main__ - INFO - Setting webhook to: https://emojournal1.onrender.com/webhook
2025-09-20 21:47:48,241 - httpx - INFO - HTTP Request: POST https://api.telegram.org/bot8028767407:AAH4dBzc8dgYPY25_yuztggbG6tY2oXHYd0/setWebhook "HTTP/1.1 200 OK"
2025-09-20 21:47:48,242 - __main__ - INFO - Webhook set successfully
2025-09-20 21:47:48,242 - __main__ - INFO - Bot started with webhook on port 8080
2025-09-20 21:47:48,242 - __main__ - INFO - Webhook URL set to: https://emojournal1.onrender.com/webhook
2025-09-20 21:47:48,242 - __main__ - INFO - Health check available at: https://emojournal1.onrender.com/health
2025-09-20 21:47:48,242 - __main__ - INFO - Root endpoint available at: https://emojournal1.onrender.com/
2025-09-20 21:47:48,662 - aiohttp.access - INFO - 127.0.0.1 [20/Sep/2025:21:47:48 +0300] "HEAD / HTTP/1.1" 200 152 "-" "Go-http-client/1.1"
     ==> Your service is live 🎉
     ==> 
     ==> ///////////////////////////////////////////////////////////
     ==> 
     ==> Available at your primary URL https://emojournal1.onrender.com
     ==> 
     ==> ///////////////////////////////////////////////////////////
2025-09-20 21:47:53,590 - aiohttp.access - INFO - 127.0.0.1 [20/Sep/2025:21:47:53 +0300] "GET / HTTP/1.1" 200 188 "-" "Go-http-client/2.0"
     ==> Deploying...
Need better ways to work with logs? Try theRender CLI, Render MCP Server, or set up a log stream integration 
