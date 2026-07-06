from django.db import migrations, models
import re

def convert_subscription_price_to_int(apps, schema_editor):
    UserSubscription = apps.get_model('accounts', 'UserSubscription')
    for sub in UserSubscription.objects.all():
        if isinstance(sub.price, str):
            # "₹299" -> 299, "299" -> 299
            price_clean = re.sub(r'[^\d]', '', str(sub.price))
            sub.price = int(price_clean) if price_clean else 0
            sub.save()

def convert_plan_price_to_int(apps, schema_editor):
    SubscriptionPlan = apps.get_model('accounts', 'SubscriptionPlan')
    for plan in SubscriptionPlan.objects.all():
        if isinstance(plan.price, str):
            price_clean = re.sub(r'[^\d]', '', str(plan.price))
            plan.price = int(price_clean) if price_clean else 0
            plan.save()

def reverse_func(apps, schema_editor):
    # Rollback വേണമെങ്കിൽ CharField ആക്കി മാറ്റാം
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0022_subscriptionplan_badge_color_and_more'),
    ]

    operations = [
        # 1. Data convert ചെയ്യുക
        migrations.RunPython(convert_plan_price_to_int, reverse_func),
        migrations.RunPython(convert_subscription_price_to_int, reverse_func),
        
        # 2. Field type മാറ്റുക
        migrations.AlterField(
            model_name='subscriptionplan',
            name='price',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='usersubscription',
            name='price',
            field=models.IntegerField(default=0),
        ),
        
        # 3. പുതിയ fields add ചെയ്യുക
        migrations.AddField(
            model_name='usersubscription',
            name='activated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='usersubscription',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]